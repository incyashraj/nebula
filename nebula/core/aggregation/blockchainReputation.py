import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import Mapping
from datetime import datetime

import requests
import torch
from eth_account import Account
from retry import retry
from tabulate import tabulate
from web3 import Web3
from web3.middleware import construct_sign_and_send_raw_middleware, geth_poa_middleware

from nebula.core.aggregation.aggregator import Aggregator
from nebula.core.utils.helper import (
    cosine_metric,
    euclidean_metric,
    jaccard_metric,
    manhattan_metric,
    minkowski_metric,
    pearson_correlation_metric,
)


def cossim_euclidean(model1, model2, similarity):
    return cosine_metric(model1, model2, similarity=similarity) * euclidean_metric(
        model1, model2, similarity=similarity
    )


class BlockchainReputation(Aggregator):
    """
    # BAT-SandrinHunkeler (BlockchainReputation)
    Weighted FedAvg by using relative reputation of each model's trainer
    Returns: aggregated model
    """

    ALGORITHM_MAP = {
        "Cossim": cosine_metric,
        "Pearson": pearson_correlation_metric,
        "Euclidean": euclidean_metric,
        "Minkowski": minkowski_metric,
        "Manhattan": manhattan_metric,
        "Jaccard": jaccard_metric,
        "CossimEuclid": cossim_euclidean,
    }

    def __init__(self, similarity_metric: str = "CossimEuclid", config=None, **kwargs):
        # initialize parent class
        super().__init__(config, **kwargs)

        self.config = config

        # extract local NEBULA name
        self.node_name = self.config.participant["network_args"]["addr"]

        # initialize BlockchainHandler for interacting with oracle and non-validator node
        self.__blockchain = BlockchainHandler(self.node_name)

        # check if node is malicious for debugging
        self.__malicious = self.config.participant["device_args"]["malicious"]

        self.__opinion_algo = BlockchainReputation.ALGORITHM_MAP.get(similarity_metric)
        self.__similarity_metric = similarity_metric

    def run_aggregation(self, model_buffer: OrderedDict[str, OrderedDict[torch.Tensor, int]]) -> torch.Tensor:
        print_with_frame("BLOCKCHAIN AGGREGATION: START")

        # track aggregation time for experiments
        start = time.time_ns()

        # verify the registration process during initialization of the BlockchainHandler
        self.__blockchain.verify_registration()

        # verify if ether balance is still sufficient for aggregating, request more otherwise
        self.__blockchain.verify_balance()

        # create dict<sender, model>
        current_models = {sender: model for sender, (model, weight) in model_buffer.items()}

        print(f"Node: {self.node_name}", flush=True)
        print(f"self.__malicious: {self.__malicious}", flush=True)

        # extract local model from models to aggregate
        local_model = model_buffer[self.node_name][0]

        # compute similarity between local model and all buffered models
        metric_values = {
            sender: max(
                min(
                    round(
                        self.__opinion_algo(local_model, current_models[sender], similarity=True),
                        5,
                    ),
                    1,
                ),
                0,
            )
            for sender in current_models
            if sender != self.node_name
        }

        # log similarity metric values
        print_table(
            "SIMILARITY METRIC",
            list(metric_values.items()),
            ["neighbour Node", f"{self.__similarity_metric} Similarity"],
        )

        # increase resolution of metric in upper half of interval
        opinion_values = {sender: round(metric**3 * 100) for sender, metric in metric_values.items()}

        # DEBUG
        if int(self.node_name[-7]) <= 1 and self.__blockchain.round >= 5:
            opinion_values = {sender: int(torch.randint(0, 101, (1,))[0]) for sender, metric in metric_values.items()}

        # push local opinions to reputation system
        self.__blockchain.push_opinions(opinion_values)

        # log pushed opinion values
        print_table(
            "REPORT LOCAL OPINION",
            list(opinion_values.items()),
            ["Node", f"Transformed {self.__similarity_metric} Similarity"],
        )

        # request global reputation values from reputation system
        reputation_values = self.__blockchain.get_reputations([sender for sender in current_models])

        # log received global reputations
        print_table(
            "GLOBAL REPUTATION",
            list(reputation_values.items()),
            ["Node", "Global Reputation"],
        )

        # normalize all reputation values to sum() == 1
        sum_reputations = sum(reputation_values.values())
        if sum_reputations > 0:
            normalized_reputation_values = {
                name: round(reputation_values[name] / sum_reputations, 3) for name in reputation_values
            }
        else:
            normalized_reputation_values = reputation_values

        # log normalized aggregation weights
        print_table(
            "AGGREGATION WEIGHTS",
            list(normalized_reputation_values.items()),
            ["Node", "Aggregation Weight"],
        )

        # initialize empty model
        final_model = {layer: torch.zeros_like(param).float() for layer, param in local_model.items()}

        # cover rare case where no models were added or reputation is 0 to return the local model
        if sum_reputations > 0:
            for sender in normalized_reputation_values.keys():
                for layer in final_model:
                    final_model[layer] += current_models[sender][layer].float() * normalized_reputation_values[sender]

        # otherwise, skip aggregation
        else:
            final_model = local_model

        # report used gas to oracle and log cumulative gas used
        print_table(
            "TOTAL GAS USED",
            self.__blockchain.report_gas_oracle(),
            ["Node", "Cumulative Gas used"],
        )
        self.__blockchain.report_time_oracle(start)

        print_with_frame("BLOCKCHAIN AGGREGATION: FINISHED")

        # return newly aggregated model
        return final_model


def print_table(title: str, values: list[tuple | list], headers: list[str]) -> None:
    """
    Prints a title, all values ordered in a table, with the headers as column titles.
    Args:
        title: Title of the table
        values: Rows of table
        headers: Column headers of table

    Returns: None, prints output

    """
    print(f"\n{'-' * 25} {title.upper()} {'-' * 25}", flush=True)
    print(tabulate(sorted(values), headers=headers, tablefmt="grid"), flush=True)


def print_with_frame(message) -> None:
    """
    Prints a large frame with a title inside
    Args:
        message: Title to put into the frame

    Returns: None

    """
    message_length = len(message)
    print(f"{' ' * 20}+{'-' * (message_length + 2)}+", flush=True)
    print(f"{'*' * 20}| {message.upper()} |{'*' * 20}", flush=True)
    print(f"{' ' * 20}+{'-' * (message_length + 2)}+", flush=True)


class BlockchainHandler:
    """
    Handles interaction with Oracle and Non-Validator Node of Blockchain Network
    """

    # static ip address of non-validator node with RPC-API
    __rpc_url = "http://172.25.0.104:8545"

    # static ip address of oracle with REST-API
    __oracle_url = "http://172.25.0.105:8081"

    # default REST header for interacting with oracle
    __rest_header = {"Content-type": "application/json", "Accept": "application/json"}

    def __init__(self, home_address):
        print_with_frame("BLOCKCHAIN INITIALIZATION: START")

        # local NEBULA name, needed for reputation system
        self.__home_ip = home_address

        # randomly generated private key, needed to sign transaction
        self.__private_key = ""

        # public wallet address generated from the private key
        self.__acc_address = ""

        # variables for experiment, not required for aggregation
        self.__gas_used = 0
        self.__gas_price = 27.3
        self.round = 1

        # generate randomized primary key
        self.__acc = self.__create_account()

        # configure web3 objects for using Proof-of-Authority
        self.__web3 = self.__initialize_web3()

        # Add basic status tracking
        self.status = {"active": False, "join_time": None, "last_seen": None}

        self.__last_status_update = datetime.now()
        self.__status_update_interval = 10  # Status update every 30 seconds
        self.__register_periodic_status_update()

        self.__optimization_metrics = {"convergence_rate": 0, "communication_overhead": 0, "aggregation_time": 0}
        self.__benchmark_data = []

        self.__aggregation_mode = "decentralized"  # or "centralized"
        self.__central_node = None

        # call Oracle to sense if blockchain is ready
        print(f"{'-' * 25} CONNECT TO ORACLE {'-' * 25}", flush=True)
        self.__wait_for_blockchain()

        # request ETH funds for creating transactions, paying gas
        self.__request_funds_from_oracle()

        # check if funds were assigned by checking directly with blockchain
        self.verify_balance()

        # request contract address and header from Oracle
        self.__contract_obj = self.__get_contract_from_oracle()

        # register public wallet address at reputation system
        print(f"{'-' * 25} CONNECT TO REPUTATION SYSTEM {'-' * 25}", flush=True)
        self.__register()
        print("BLOCKCHAIN: Registered to reputation system", flush=True)

        # check if registration was successful
        self.verify_registration()
        print("BLOCKCHAIN: Verified registration", flush=True)

        print_with_frame("BLOCKCHAIN INITIALIZATION: FINISHED")

    @classmethod
    @property
    def oracle_url(cls) -> str:
        return cls.__oracle_url

    @classmethod
    @property
    def rest_header(cls) -> Mapping[str, str]:
        return cls.__rest_header

    def __create_account(self):
        """
        Generates randomized primary key and derives public account from it
        Returns: None

        """
        print(f"{'-' * 25} REGISTER WORKING NODE {'-' * 25}", flush=True)

        # generate random private key, address, public address
        acc = Account.create()

        # initialize web3 utility object
        web3 = Web3()

        # convert private key to hex, used in raw transactions
        self.__private_key = web3.to_hex(acc.key)

        # convert address type, used in raw transactions
        self.__acc_address = web3.to_checksum_address(acc.address)

        print(f"WORKER NODE: Registered account: {self.__home_ip}", flush=True)
        print(f"WORKER NODE: Account address: {self.__acc_address}", flush=True)

        # return generated account
        return acc

    def __initialize_web3(self):
        """
        Initializes Web3 object and configures it for PoA protocol
        Returns: Web3 object

        """

        # initialize Web3 object with ip of non-validator node
        web3 = Web3(Web3.HTTPProvider(self.__rpc_url, request_kwargs={"timeout": 20}))  # 10

        # inject Proof-of-Authority settings to object
        web3.middleware_onion.inject(geth_poa_middleware, layer=0)

        # automatically sign transactions if available for execution
        web3.middleware_onion.add(construct_sign_and_send_raw_middleware(self.__acc))

        # inject local account as default
        web3.eth.default_account = self.__acc_address

        # return initialized object for executing transaction
        return web3

    @retry((Exception, requests.exceptions.HTTPError), tries=20, delay=4)
    def __wait_for_blockchain(self) -> None:
        """
        Request state of blockchain from Oracle by periodic calls and sleep
        Returns: None

        """

        # check with oracle if blockchain is ready for requests
        response = requests.get(
            url=f"{self.__oracle_url}/status",
            headers=self.__rest_header,
            timeout=20,  # 10
        )

        # raise Exception if status is not successful
        response.raise_for_status()

        return print("ORACLE: Blockchain is ready", flush=True)

    @retry((Exception, requests.exceptions.HTTPError), tries=3, delay=4)
    def __request_funds_from_oracle(self) -> None:
        """
        Requests funds from Oracle by sending public address
        Returns: None

        """

        # call oracle's faucet by Http post request
        response = requests.post(
            url=f"{self.__oracle_url}/faucet",
            json={"address": self.__acc_address},
            headers=self.__rest_header,
            timeout=20,  # 10
        )

        # raise Exception if status is not successful
        response.raise_for_status()

        return print("ORACLE: Received 500 ETH", flush=True)

    def verify_balance(self) -> None:
        """
        Calls blockchain directly for requesting current balance
        Returns: None

        """

        # directly call view method from non-validator node
        balance = self.__web3.eth.get_balance(self.__acc_address, "latest")

        # convert wei to ether
        balance_eth = self.__web3.from_wei(balance, "ether")
        print(
            f"BLOCKCHAIN: Successfully verified balance of {balance_eth} ETH",
            flush=True,
        )

        # if node ran out of funds, it requests ether from the oracle
        if balance_eth <= 1:
            self.__request_funds_from_oracle()

        return None

    @retry((Exception, requests.exceptions.HTTPError), tries=3, delay=4)
    def __get_contract_from_oracle(self):
        """
        Requests header file and contract address, generates Web3 Contract object with it
        Returns: Web3 Contract object

        """

        response = requests.get(
            url=f"{self.__oracle_url}/contract",
            headers=self.__rest_header,
            timeout=20,  # 10
        )

        # raise Exception if status is not successful
        response.raise_for_status()

        # convert response to json to extract the abi and address
        json_response = response.json()

        print(
            f"ORACLE: Initialized chain code: {json_response.get('address')}",
            flush=True,
        )

        # return an initialized web3 contract object
        return self.__web3.eth.contract(abi=json_response.get("abi"), address=json_response.get("address"))

    @retry((Exception, requests.exceptions.HTTPError), tries=3, delay=4)
    def report_gas_oracle(self) -> list:
        """
        Reports accumulated gas costs of all transactions made to the blockchain
        Returns: List of all accumulated gas costs per registered node

        """

        # method used for experiments, not needed for aggregation
        response = requests.post(
            url=f"{self.__oracle_url}/gas",
            json={"amount": self.__gas_used, "round": self.round},
            headers=self.__rest_header,
            timeout=20,  # 10
        )

        # raise Exception if status is not successful
        response.raise_for_status()

        # reset local gas accumulation
        self.__gas_used = 0

        # return list with gas usage for logging
        return list(response.json().items())

    @retry((Exception, requests.exceptions.HTTPError), tries=3, delay=4)
    def report_reputation_oracle(self, records: list) -> None:
        """
        Reports reputations used for aggregation
        Returns: None

        """

        # method used for experiments, not needed for aggregation
        response = requests.post(
            url=f"{self.__oracle_url}/reputation",
            json={"records": records, "round": self.round, "sender": self.__home_ip},
            headers=self.__rest_header,
            timeout=20,  # 10
        )

        # raise Exception if status is not successful
        response.raise_for_status()

        return None

    def __sign_and_deploy(self, trx_hash):
        """
        Signs a function call to the chain code with the primary key and awaits the receipt
        Args:
            trx_hash: Transformed dictionary of all properties relevant for call to chain code

        Returns: transaction receipt confirming the successful write to the ledger

        """

        # transaction is signed with private key
        signed_transaction = self.__web3.eth.account.sign_transaction(trx_hash, private_key=self.__private_key)

        # confirmation that transaction was passed from non-validator node to validator nodes
        executed_transaction = self.__web3.eth.send_raw_transaction(signed_transaction.rawTransaction)

        # non-validator node awaited the successful validation by validation nodes and returns receipt
        transaction_receipt = self.__web3.eth.wait_for_transaction_receipt(executed_transaction)

        # accumulate used gas
        self.__gas_used += transaction_receipt.gasUsed

        return transaction_receipt

    @retry(Exception, tries=3, delay=4)
    def push_opinions(self, opinion_dict: dict):
        """
        Pushes all locally computed opinions of models to aggregate to the reputation system
        Args:
            opinion_dict: Dict of all names:opinions for writing to the reputation system

        Returns: Json of transaction receipt

        """

        if self.__should_update_status():
            self.update_status()
            self.report_status_to_oracle()
            self.__last_status_update = datetime.now()

        # create raw transaction object to call rate_neighbors() from the reputation system
        unsigned_trx = self.__contract_obj.functions.rate_neighbours(list(opinion_dict.items())).build_transaction({
            "chainId": self.__web3.eth.chain_id,
            "from": self.__acc_address,
            "nonce": self.__web3.eth.get_transaction_count(
                self.__web3.to_checksum_address(self.__acc_address), "pending"
            ),
            "gasPrice": self.__web3.to_wei(self.__gas_price, "gwei"),
        })

        # sign and execute the transaction
        conf = self.__sign_and_deploy(unsigned_trx)

        self.report_reputation_oracle(list(opinion_dict.items()))
        # return the receipt as json
        return self.__web3.to_json(conf)

    @retry(Exception, tries=3, delay=4)
    def get_reputations(self, ip_addresses: list) -> dict:
        """
        Requests globally aggregated opinions values from reputation system for computing aggregation weights
        Args:
            ip_addresses: Names of nodes of which the reputation values should be generated

        Returns: Dictionary of name:reputation from the reputation system

        """

        if self.__should_update_status():
            self.update_status()
            self.report_status_to_oracle()
            self.__last_status_update = datetime.now()

        final_reputations = dict()
        stats_to_print = list()

        # call get_reputations() from reputation system
        raw_reputation = self.__contract_obj.functions.get_reputations(ip_addresses).call({"from": self.__acc_address})

        # loop list with tuples from reputation system
        for (
            name,
            reputation,
            weighted_reputation,
            stddev_count,
            divisor,
            final_reputation,
            avg,
            median,
            stddev,
            index,
            avg_deviation,
            avg_avg_deviation,
            malicious_opinions,
        ) in raw_reputation:
            # list elements with an empty name can be ignored
            if not name:
                continue

            # print statistical values
            stats_to_print.append([
                name,
                reputation / 10,
                weighted_reputation / 10,
                stddev_count / 10,
                divisor / 10,
                final_reputation / 10,
                avg / 10,
                median / 10,
                stddev / 10,
                avg_deviation / 10,
                avg_avg_deviation / 10,
                malicious_opinions,
            ])

            # assign the final reputation to a dict for later aggregation
            final_reputations[name] = final_reputation / 10

        print_table(
            "REPUTATION SYSTEM STATE",
            stats_to_print,
            [
                "Name",
                "Reputation",
                "Weighted Rep. by local Node",
                "Stddev Count",
                "Divisor",
                "Final Reputation",
                "Mean",
                "Median",
                "Stddev",
                "Avg Deviation in Opinion",
                "Avg of all Avg Deviations in Opinions",
                "Malicious Opinions",
            ],
        )

        # if sum(final_reputations.values()):
        #     self.report_reputation_oracle(list(final_reputations.items()))

        return final_reputations

    @retry(Exception, tries=3, delay=4)
    def __register(self) -> str:
        """
        Registers a node's name with its public address, signed with private key
        Returns: Json of transaction receipt

        """

        # build raw transaction object to call public method register() from reputation system
        unsigned_trx = self.__contract_obj.functions.register(self.__home_ip).build_transaction({
            "chainId": self.__web3.eth.chain_id,
            "from": self.__acc_address,
            "nonce": self.__web3.eth.get_transaction_count(
                self.__web3.to_checksum_address(self.__acc_address), "pending"
            ),
            "gasPrice": self.__web3.to_wei(self.__gas_price, "gwei"),
        })

        self.status["active"] = True
        self.status["join_time"] = datetime.now()
        self.status["last_seen"] = datetime.now()

        # sign and execute created transaction
        conf = self.__sign_and_deploy(unsigned_trx)

        # return the receipt as json
        return self.__web3.to_json(conf)

    @retry(Exception, tries=3, delay=4)
    def verify_registration(self) -> None:
        """
        Verifies the successful registration of the node itself,
        executes registration again if reputation system returns false
        Returns: None

        """

        # call view function of reputation system to check if registration was not abandoned by hard fork
        confirmation = self.__contract_obj.functions.confirm_registration().call({"from": self.__acc_address})

        # function returns boolean
        if not confirmation:
            # register again if not successful
            self.__register()

            # raise Exception to check again
            raise Exception("EXCEPTION: _verify_registration() => Could not be confirmed)")

        # Report initial status after successful registration
        self.report_status_to_oracle()

        return None

    @retry((Exception, requests.exceptions.HTTPError), tries=3, delay=4)
    def report_time_oracle(self, start: float) -> None:
        """
        Reports time used for aggregation
        Returns: None

        """
        # method used for experiments, not needed for aggregation
        # report aggregation time and round to oracle
        response = requests.post(
            url=f"{BlockchainHandler.oracle_url}/time",
            json={"time": (time.time_ns() - start) / (10**9), "round": self.round},
            headers=self.__rest_header,
            timeout=20,  # 10
        )

        # raise Exception if status is not successful
        response.raise_for_status()

        # increase aggregation round counter after reporting time
        self.round += 1
        return None

    def update_status(self):
        """Update client's last seen timestamp"""
        current_time = datetime.now()
        self.status["last_seen"] = current_time
        logging.info(f"Status updated - Last seen: {current_time.isoformat()}")

    def is_active(self):
        """Check if client is still active based on last_seen"""
        if not self.status["last_seen"]:
            return False
        # Consider client inactive if not seen in last 60 seconds
        return (datetime.now() - self.status["last_seen"]).total_seconds() < 60

    def get_status_report(self):
        """Get comprehensive status report for client"""
        current_time = datetime.now()
        uptime = None
        if self.status["join_time"]:
            uptime = (current_time - self.status["join_time"]).total_seconds()

        return {
            "client_id": self.__home_ip,
            "active": self.is_active(),
            "join_time": self.status["join_time"].isoformat() if self.status["join_time"] else None,
            "last_seen": self.status["last_seen"].isoformat() if self.status["last_seen"] else None,
            "uptime_seconds": uptime,
            "gas_used": self.__gas_used,  # Using existing gas tracking
            "aggregation_round": self.round,  # Using existing round tracking
        }

    def report_status_to_oracle(self):
        """Report client status to Oracle"""
        try:
            status_data = self.get_status_report()
            logging.info(f"Sending status update to Oracle: {status_data}")
            response = requests.post(
                url=f"{self.__oracle_url}/client_status", json=status_data, headers=self.__rest_header, timeout=20
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.exception(f"Failed to report status to Oracle: {e}")
            return None

    def __should_update_status(self):
        """Check if it's time for a status update"""
        now = datetime.now()
        time_since_update = (now - self.__last_status_update).total_seconds()
        should_update = time_since_update >= self.__status_update_interval
        if should_update:
            logging.info(f"Time for status update. Time since last update: {time_since_update}s")
        return should_update

    def __register_periodic_status_update(self):
        """Register the periodic status update task"""
        asyncio.create_task(self.__periodic_status_update())

    async def __periodic_status_update(self):
        """Periodic task to update status"""
        while True:
            try:
                if self.__should_update_status():
                    logging.info("Performing periodic status update")
                    self.update_status()
                    self.report_status_to_oracle()
                    self.__last_status_update = datetime.now()
            except Exception as e:
                logging.exception(f"Error in periodic status update: {e}")
            await asyncio.sleep(5)  # Check every 5 seconds

    def get_selected_clients(self, num_clients=None, criteria="random"):
        """Get selected clients for current round"""
        try:
            params = {"num_clients": num_clients, "criteria": criteria}
            response = requests.get(
                url=f"{self.__oracle_url}/select_clients", params=params, headers=self.__rest_header, timeout=20
            )
            return response.json()
        except Exception as e:
            logging.exception(f"Error getting selected clients: {e}")
            return []

    def track_model_version(self):
        data = {
            "client_id": self.__home_ip,
            "local_version": self.round,
            "global_version": self.__global_version,
            "timestamp": datetime.now().isoformat(),
            "performance": self.__latest_performance,
        }
        try:
            response = requests.post(url=f"{self.__oracle_url}/model/version", json=data, headers=self.__rest_header)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.exception(f"Failed to track model version: {e}")
            return None

    def check_performance_and_replace(self, current_performance):
        try:
            # Report performance to Oracle
            data = {"client_id": self.__home_ip, "performance": current_performance}
            response = requests.post(f"{self.__oracle_url}/model/performance", json=data, headers=self.__rest_header)

            if response.json().get("replace_model", False):
                self.handle_model_replacement()

        except Exception as e:
            logging.exception(f"Performance check failed: {e}")

    def handle_model_replacement(self):
        logging.info("Starting model replacement")
        self.__global_version += 1
        # Trigger retraining

    def sync_model_versions(self):
        """Sync local and global model versions"""
        try:
            response = requests.get(f"{self.__oracle_url}/model/versions/{self.__home_ip}", headers=self.__rest_header)
            versions = response.json()
            if versions["current_global"] > self.__global_version:
                logging.info(f"New global version available: {versions['current_global']}")
                return self.handle_model_replacement()
            return False
        except Exception as e:
            logging.exception(f"Version sync failed: {e}")
            return False

    def get_model_state(self, version):
        """Get model state from oracle"""
        try:
            response = requests.get(f"{self.__oracle_url}/model/state/{version}", headers=self.__rest_header)
            return response.json().get("model_state")
        except Exception as e:
            logging.exception(f"Failed to get model state: {e}")
            return None

    def sync_model_state(self):
        """Sync model state with latest version"""
        latest = self.get_latest_model_version()
        if latest["version"] > self.__global_version:
            model_state = self.get_model_state(latest["version"])
            if model_state:
                self.__current_model = model_state
                self.__global_version = latest["version"]
                return True
        return False

    async def aggregate_with_version_sync(self):
        """Aggregation with version syncing"""
        if await self.sync_model_state():
            logging.info("Model state updated, restarting training")
            return True

        performance = await self.calculate_performance()
        if performance < self.__performance_threshold:
            await self.check_performance_and_replace(performance)

        await self.track_model_version()
        return False

    def optimize_aggregation(self):
        """Adjust aggregation parameters based on benchmarks"""
        try:
            # Get optimization suggestions from Oracle
            response = requests.post(
                f"{self.__oracle_url}/optimization/benchmark",
                json={"client_id": self.__home_ip, "metrics": self.__optimization_metrics},
                headers=self.__rest_header,
            )

            suggestions = response.json()

            if suggestions.get("optimize_batch_size"):
                self.__adjust_batch_size()

            if suggestions.get("adjust_learning_rate"):
                self.__adjust_learning_rate()

            return suggestions

        except Exception as e:
            logging.exception(f"Optimization failed: {e}")
            return {}

    def __adjust_batch_size(self):
        """Adjust batch size based on communication overhead"""
        current_overhead = self.__optimization_metrics["communication_overhead"]
        if current_overhead > 1000:  # threshold
            self.__batch_size = max(32, self.__batch_size // 2)
        else:
            self.__batch_size = min(256, self.__batch_size * 2)

    def __adjust_learning_rate(self):
        """Adjust learning rate based on convergence"""
        current_rate = self.__optimization_metrics["convergence_rate"]
        if current_rate < 0.001:  # threshold
            self.__learning_rate *= 1.5
        else:
            self.__learning_rate *= 0.8

    async def optimized_aggregation(self):
        """Perform aggregation with optimization"""
        start_time = time.time()

        try:
            # Regular aggregation
            result = await self.aggregate_with_version_sync()

            # Update metrics
            self.__optimization_metrics.update({
                "aggregation_time": time.time() - start_time,
                "convergence_rate": self._calculate_convergence_rate(),
                "communication_overhead": self._calculate_communication_overhead(),
            })

            # Benchmark and optimize
            await self.benchmark_performance()
            optimization_result = self.optimize_aggregation()

            logging.info(f"Optimization metrics: {self.__optimization_metrics}")
            logging.info(f"Optimization suggestions: {optimization_result}")

            return result

        except Exception as e:
            logging.exception(f"Optimized aggregation failed: {e}")
            return False

    def _calculate_convergence_rate(self):
        """Calculate convergence rate from recent rounds"""
        if len(self.__benchmark_data) < 2:
            return 0

        recent = self.__benchmark_data[-2:]
        return abs(recent[1].get("performance", 0) - recent[0].get("performance", 0))

    def _calculate_communication_overhead(self):
        """Calculate communication overhead"""
        return sum(len(str(d)) for d in self.__benchmark_data[-1:])  # Simple estimation

    async def set_aggregation_mode(self, mode, central_node=None):
        """Switch between centralized and decentralized modes"""
        if mode not in ["centralized", "decentralized"]:
            logging.error(f"Invalid aggregation mode: {mode}")
            return False

        self.__aggregation_mode = mode
        self.__central_node = central_node

        # Update Oracle about mode change
        await self.report_mode_change(mode)
        return True

    async def optimized_aggregation(self):
        """Updated aggregation with mode awareness"""
        if self.__aggregation_mode == "centralized":
            return await self._centralized_aggregation()
        else:
            return await self._decentralized_aggregation()

    async def _centralized_aggregation(self):
        """Centralized aggregation mode"""
        try:
            if self.__central_node:
                # If this is central node
                if self.__home_ip == self.__central_node:
                    logging.info("Acting as central aggregator")
                    # Collect models from all nodes
                    models = await self._collect_models()
                    # Aggregate
                    return await self._aggregate_models(models)
                else:
                    # Send model to central node
                    logging.info(f"Sending model to central node: {self.__central_node}")
                    return await self._send_model_to_central()
        except Exception as e:
            logging.exception(f"Centralized aggregation failed: {e}")
            return False

    async def _decentralized_aggregation(self):
        """Decentralized aggregation mode"""
        try:
            # Get active neighbors
            active_nodes = await self.get_active_nodes()
            if not active_nodes:
                logging.warning("No active nodes for decentralized aggregation")
                return False

            # Exchange models with neighbors
            neighbor_models = await self._exchange_models(active_nodes)

            # Local aggregation
            return await self._aggregate_models(neighbor_models)
        except Exception as e:
            logging.exception(f"Decentralized aggregation failed: {e}")
            return False
