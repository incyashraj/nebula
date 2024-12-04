import json
import logging
import os
import random
from collections.abc import Mapping
from datetime import datetime
from functools import wraps

import requests
from eth_account import Account
from flask import Flask, jsonify, request
from retry import retry
from solcx import compile_standard, install_solc
from web3 import Web3
from web3.middleware import construct_sign_and_send_raw_middleware, geth_poa_middleware

app = Flask(__name__)


def error_handler(func):
    """Adds default status and header to all REST responses used for Oracle"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs), 200, {"Content-Type": "application/json"}
        except Exception as e:
            return jsonify({"error": str(e)}), 500, {"Content-Type": "application/json"}

    return wrapper


class Oracle:
    def __init__(self):
        # header file, required for interacting with chain code
        self.__contract_abi = dict()

        # stores gas expenses for experiments
        self.__gas_store = list()

        # stores timing records for experiments
        self.__time_store = list()

        # stores reputation records for experiments
        self.__reputation_store = list()

        # current (03.2024) average amount of WEI to pay for a unit of gas
        self.__gas_price_per_unit = 27.3

        # current (03.2024) average price in USD per WEI
        self.__price_USD_per_WEI = 0.00001971

        # static ip address of non-validator node (RPC)
        self.__blockchain_address = "http://172.25.0.104:8545"

        # executes RPC request to non-validator node until ready
        self.__ready = self.wait_for_blockchain()

        # creates an account from the primary key stored in the envs
        self.acc = self.__create_account()

        # create Web3 object for making transactions
        self.__web3 = self.__initialize_web3()

        self.__aggregation_mode = "decentralized"
        self.__central_node = None
        self.__mode_history = []

        # Add client status storage
        self.__client_status = {}  # Store client statuses
        self.__active_clients = set()  # Track active clients
        self.__inactive_timeout = 600  # 60 seconds timeout

        self.__model_registry = {}  # Store model versions
        self.__global_version = 0  # Track global model version

        self.__performance_threshold = 0.8
        self.__performance_history = {}

        self.__model_states = {}  # Add this line

        self.__benchmark_data = {}
        self.__optimization_thresholds = {
            "convergence_rate": 0.001,  # Minimum improvement rate
            "communication_overhead": 1000,  # Maximum bytes
            "aggregation_time": 60,  # Maximum seconds
        }

        # create a Web3 contract object from the compiled chaincode
        self.contract_obj = self.__compile_chaincode()

        # deploy the contract to the blockchain network
        self.__contract_address = self.deploy_chaincode()

        # update the contract object with the address
        self.contract_obj = self.__web3.eth.contract(
            abi=self.contract_obj.abi,
            bytecode=self.contract_obj.bytecode,
            address=self.contract_address,
        )

    @property
    def contract_abi(self):
        return self.__contract_abi

    @property
    def contract_address(self):
        return self.__contract_address

    @retry((Exception, requests.exceptions.HTTPError), tries=20, delay=10)
    def wait_for_blockchain(self) -> bool:
        """
        Executes REST post request for a selected RPC method to check if blockchain
        is up and running
        Returns: None

        """
        headers = {"Content-type": "application/json", "Accept": "application/json"}

        data = {"jsonrpc": "2.0", "method": "eth_accounts", "id": 1, "params": []}

        request = requests.post(url=self.__blockchain_address, json=data, headers=headers)

        # raise Exception if status is an error one
        request.raise_for_status()

        print("ORACLE: RPC node up and running", flush=True)

        return True

    def __initialize_web3(self):
        """
        Initializes Web3 object and configures it for PoA protocol
        Returns: Web3 object

        """

        # initialize Web3 object with ip of non-validator node
        web3 = Web3(Web3.HTTPProvider(self.__blockchain_address, request_kwargs={"timeout": 20}))  # 10

        # inject Proof-of-Authority settings to object
        web3.middleware_onion.inject(geth_poa_middleware, layer=0)

        # automatically sign transactions if available for execution
        web3.middleware_onion.add(construct_sign_and_send_raw_middleware(self.acc))

        # inject local account as default
        web3.eth.default_account = self.acc.address

        # return initialized object for executing transaction
        print(f"SUCCESS: Account created at {self.acc.address}")
        return web3

    def __compile_chaincode(self):
        """
        Compile raw chaincode and create Web3 contract object with it
        Returns: Web3 contract object

        """

        # open raw solidity file
        with open("reputation_system.sol") as file:
            simple_storage_file = file.read()

        # set compiler version
        install_solc("0.8.22")

        # compile solidity code
        compiled_sol = compile_standard(
            {
                "language": "Solidity",
                "sources": {"reputation_system.sol": {"content": simple_storage_file}},
                "settings": {
                    "evmVersion": "paris",
                    "outputSelection": {"*": {"*": ["abi", "metadata", "evm.bytecode", "evm.sourceMap"]}},
                    "optimizer": {"enabled": True, "runs": 1000},
                },
            },
            solc_version="0.8.22",
        )

        # store compiled code as json
        with open("compiled_code.json", "w") as file:
            json.dump(compiled_sol, file)

        # retrieve bytecode from the compiled contract
        contract_bytecode = compiled_sol["contracts"]["reputation_system.sol"]["ReputationSystem"]["evm"]["bytecode"][
            "object"
        ]

        # retrieve ABI from compiled contract
        self.__contract_abi = json.loads(
            compiled_sol["contracts"]["reputation_system.sol"]["ReputationSystem"]["metadata"]
        )["output"]["abi"]

        print("Oracle: Solidity files compiled and bytecode ready", flush=True)

        # return draft Web3 contract object
        return self.__web3.eth.contract(abi=self.__contract_abi, bytecode=contract_bytecode)

    @staticmethod
    def __create_account():
        """
        Retrieves the private key from the envs, set during docker build
        Returns: Web3 account object

        """

        # retrieve private key, set during ducker build
        private_key = os.environ.get("PRIVATE_KEY")

        # return Web3 account object
        return Account.from_key("0x" + private_key)

    @retry((Exception, requests.exceptions.HTTPError), tries=3, delay=4)
    def transfer_funds(self, address):
        """
        Creates transaction to blockchain network for assigning funds to Cores
        Args:
            address: public wallet address of Core to assign funds to

        Returns: Transaction receipt

        """

        # create raw transaction with all required parameters to change state of ledger
        raw_transaction = {
            "chainId": self.__web3.eth.chain_id,
            "from": self.acc.address,
            "value": self.__web3.to_wei("500", "ether"),
            "to": self.__web3.to_checksum_address(address),
            "nonce": self.__web3.eth.get_transaction_count(self.acc.address, "pending"),
            "gasPrice": self.__web3.to_wei(self.__gas_price_per_unit, "gwei"),
            "gas": self.__web3.to_wei("22000", "wei"),
        }

        # sign transaction with private key and execute it
        tx_receipt = self.__sign_and_deploy(raw_transaction)

        # return transaction receipt
        return f"SUCESS: {tx_receipt}"

    def __sign_and_deploy(self, trx_hash):
        """
        Signs a function call to the chain code with the primary key and awaits the receipt
        Args:
            trx_hash: Transformed dictionary of all properties relevant for call to chain code

        Returns: transaction receipt confirming the successful write to the ledger

        """

        # transaction is signed with private key
        signed_transaction = self.__web3.eth.account.sign_transaction(trx_hash, private_key=self.acc.key)

        # confirmation that transaction was passed from non-validator node to validator nodes
        executed_transaction = self.__web3.eth.send_raw_transaction(signed_transaction.rawTransaction)

        # non-validator node awaited the successful validation by validation nodes and returns receipt
        transaction_receipt = self.__web3.eth.wait_for_transaction_receipt(executed_transaction, timeout=20)  # 5

        # report used gas for experiment
        self.report_gas(transaction_receipt.gasUsed, 0)

        return transaction_receipt

    @retry(Exception, tries=20, delay=5)
    def deploy_chaincode(self):
        """
        Creates transaction to deploy chain code on the blockchain network by
        sending transaction to non-validator node
        Returns: address of chain code on the network

        """

        # create raw transaction with all properties to deploy contract
        raw_transaction = self.contract_obj.constructor().build_transaction({
            "chainId": self.__web3.eth.chain_id,
            "from": self.acc.address,
            "value": self.__web3.to_wei("3", "ether"),
            "gasPrice": self.__web3.to_wei(self.__gas_price_per_unit, "gwei"),
            "nonce": self.__web3.eth.get_transaction_count(self.acc.address, "pending"),
        })

        # sign transaction with private key and executes it
        tx_receipt = self.__sign_and_deploy(raw_transaction)

        # store the address received from the non-validator node
        contract_address = tx_receipt["contractAddress"]

        # returns contract address to provide to the cores later
        return contract_address

    def get_balance(self, addr):
        """
        Creates transaction to blockchain network to request balance for parameter address
        Args:
            addr: public wallet address of account

        Returns: current balance in ether (ETH)

        """

        # converts address type required for making a transaction
        cAddr = self.__web3.to_checksum_address(addr)

        # executes the transaction directly, no signing required
        balance = self.__web3.eth.get_balance(cAddr, "pending")

        # returns JSON response with ether balance to requesting core
        return {"address": cAddr, "balance_eth": self.__web3.from_wei(balance, "ether")}

    def report_gas(self, amount: int, aggregation_round: int) -> None:
        """
        Experiment method for collecting and reporting gas usage statistics
        Args:
            aggregation_round: Aggregation round of sender
            amount: Amount of gas spent in WEI

        Returns: None

        """

        # store the recorded gas for experiment
        self.__gas_store.append((amount, aggregation_round))

    def get_gas_report(self) -> Mapping[str, str]:
        """
        Experiment method for requesting the summed up records of reported gas usage
        Returns: JSON with name:value (WEI/USD) for every reported node

        """
        # sum up all reported costs
        total_wei = sum(record[0] for record in self.__gas_store)

        # convert sum in WEI to USD by computing with gas price USD per WEI
        total_usd = round(total_wei * self.__price_USD_per_WEI)

        return {"Sum (WEI)": total_wei, "Sum (USD)": f"{total_usd:,}"}

    @property
    def gas_store(self):
        """
        Experiment method for requesting the detailed records of the gas reports
        Returns: list of records of type: list[(node, timestamp, gas)]

        """
        return self.__gas_store

    def report_time(self, time_s: float, aggregation_round: int) -> None:
        """
        Experiment method for collecting and reporting time statistics
        Args:
            aggregation_round: Aggregation round of node
            method: Name of node which reports time
            time_s: Amount of time spend on method

        Returns: None

        """

        # store the recorded time for experiment
        self.__time_store.append((time_s, aggregation_round))

    def report_reputation(self, records: list, aggregation_round: int, sender: str) -> None:
        """
        Experiment method for collecting and reporting reputations statistics
        Args:
            aggregation_round: Current aggregation round of sender
            records: list of (name:reputation) records
            sender: node reporting its local view

        Returns: None

        """

        # store the recorded reputation for experiment
        self.__reputation_store.extend([(record[0], record[1], aggregation_round, sender) for record in records])

    @property
    def time_store(self) -> list:
        """
        Experiment method for requesting all records of nodes which reported timings
        Returns: JSON with method:(sum_time, n_calls) for every reported node

        """
        return self.__time_store

    @property
    def reputation_store(self) -> list:
        """
        Experiment method for requesting all records of reputations
        Returns: list with (name, reputation, timestamp)

        """
        return self.__reputation_store

    @property
    def ready(self) -> bool:
        """
        Returns true if the Oracle is ready itself and the chain code was deployed successfully
        Returns: True if ready False otherwise

        """
        return self.__ready

    def is_client_active(self, last_seen_str):
        """Check if client is still active based on last_seen time"""
        try:
            last_seen = datetime.fromisoformat(last_seen_str)
            time_since_update = (datetime.now() - last_seen).total_seconds()
            is_active = time_since_update < self.__inactive_timeout
            logging.info(
                f"Checking active status: last_seen={last_seen_str}, time_since_update={time_since_update}, timeout={self.__inactive_timeout}, is_active={is_active}"
            )
            return is_active
        except Exception as e:
            logging.exception(f"Error checking client active status: {e}")
            return False

    def update_client_status(self, status_data):
        """Update and store client status"""
        client_id = status_data["client_id"]
        try:
            current_time = datetime.now()
            last_seen = datetime.fromisoformat(status_data["last_seen"])
            time_since_update = (current_time - last_seen).total_seconds()

            # Mark active if seen in last 5 minutes
            status_data["active"] = time_since_update < self.__inactive_timeout
            if status_data["active"]:
                self.__active_clients.add(client_id)
            else:
                self.__active_clients.discard(client_id)

            self.__client_status[client_id] = status_data

            print(
                f"Client {client_id}: last_seen={last_seen}, time_since={time_since_update}s, active={status_data['active']}"
            )

            return {
                "total_clients": len(self.__client_status),
                "active_clients": len(self.__active_clients),
                "time_since_update": time_since_update,
            }
        except Exception as e:
            print(f"Error updating client status: {e}")
            return None

    def get_active_clients(self):
        """Get list of currently active clients"""
        return list(self.__active_clients)

    def get_all_client_status(self):
        """Get status of all clients, updating active status"""
        for client_id, status in self.__client_status.items():
            if not self.is_client_active(status["last_seen"]):
                status["active"] = False
                self.__active_clients.discard(client_id)
            else:
                status["active"] = True
                self.__active_clients.add(client_id)
        return self.__client_status

    def select_clients(self, num_clients=None, selection_criteria="random"):
        """Select eligible clients for training round"""
        active_clients = list(self.__active_clients)

        if not active_clients:
            return []

        if not num_clients:
            num_clients = len(active_clients)

        # Get latest statuses
        client_statuses = self.get_all_client_status()

        # Filter based on criteria
        eligible_clients = []
        for client in active_clients:
            status = client_statuses.get(client, {})
            # Basic eligibility checks
            if status.get("active") and status.get("uptime_seconds", 0) > 30:
                eligible_clients.append(client)

        # Select clients based on strategy
        if selection_criteria == "random":
            return random.sample(eligible_clients, min(num_clients, len(eligible_clients)))
        elif selection_criteria == "reputation":
            # Sort by gas usage as simple reputation metric
            sorted_clients = sorted(eligible_clients, key=lambda x: client_statuses[x].get("gas_used", 0))
            return sorted_clients[:num_clients]

        return eligible_clients[:num_clients]

    def register_model_version(self, data):
        """
        Register a model version
        data = {
            'client_id': str,
            'local_version': int,
            'global_version': int,
            'timestamp': str,
            'performance': float
        }
        """
        client_id = data["client_id"]
        if client_id not in self.__model_registry:
            self.__model_registry[client_id] = []
        self.__model_registry[client_id].append(data)
        return {"status": "success", "global_version": self.__global_version}

    def get_model_versions(self, client_id):
        return {"versions": self.__model_registry.get(client_id, []), "current_global": self.__global_version}

    def update_global_version(self):
        self.__global_version += 1
        return self.__global_version

    def check_model_performance(self, client_id, performance):
        """Monitor model performance and detect degradation"""
        if client_id not in self.__performance_history:
            self.__performance_history[client_id] = []

        self.__performance_history[client_id].append(performance)

        # Check for degradation
        if len(self.__performance_history[client_id]) >= 3:
            recent = self.__performance_history[client_id][-3:]
            if all(p < self.__performance_threshold for p in recent):
                return True
        return False

    def trigger_model_replacement(self, client_id):
        """Trigger new training when performance drops"""
        logging.info(f"Triggering model replacement for {client_id}")
        self.__global_version += 1
        return {"new_version": self.__global_version}

    def get_latest_model_version(self):
        """Get latest model state"""
        return {
            "version": self.__global_version,
            "performance_threshold": self.__performance_threshold,
            "active_clients": len(self.__active_clients),
        }

    def get_model_state(self, version):
        return self.__model_states.get(str(version))

    def update_model_state(self, data):
        version = str(data["version"])
        self.__model_states[version] = data["state"]
        return {"version": version}

    def handle_model_update(self, client_id, model_state, performance):
        """Handle model update with version control"""
        needs_replacement = self.check_model_performance(client_id, performance)
        if needs_replacement:
            new_version = self.trigger_model_replacement(client_id)
            self.update_model_state({"version": new_version, "state": model_state})

    def store_benchmark_data(self, client_id, data):
        """Store benchmark data from clients"""
        if client_id not in self.__benchmark_data:
            self.__benchmark_data[client_id] = []
        self.__benchmark_data[client_id].append(data)

        return self.optimize_parameters(client_id)

    def optimize_parameters(self, client_id):
        """Optimize based on benchmark data"""
        if not self.__benchmark_data.get(client_id):
            return {}

        recent_data = self.__benchmark_data[client_id][-5:]  # Last 5 rounds

        # Calculate optimization metrics
        avg_convergence = sum(d["convergence_rate"] for d in recent_data) / len(recent_data)
        avg_overhead = sum(d["communication_overhead"] for d in recent_data) / len(recent_data)

        # Return optimization suggestions
        return {
            "optimize_batch_size": avg_overhead > self.__optimization_thresholds["communication_overhead"],
            "adjust_learning_rate": avg_convergence < self.__optimization_thresholds["convergence_rate"],
        }

    def get_optimization_history(self, client_id):
        """Get optimization history for a client"""
        return {
            "benchmark_data": self.__benchmark_data.get(client_id, []),
            "optimization_thresholds": self.__optimization_thresholds,
            "total_optimizations": len(self.__benchmark_data.get(client_id, [])),
        }

    def update_aggregation_mode(self, data):
        """Update system aggregation mode"""
        mode = data.get("mode")
        central_node = data.get("central_node")

        if mode not in ["centralized", "decentralized"]:
            return {"error": "Invalid mode"}

        self.__aggregation_mode = mode
        self.__central_node = central_node if mode == "centralized" else None

        self.__mode_history.append({
            "timestamp": datetime.now().isoformat(),
            "mode": mode,
            "central_node": central_node,
        })

        return {"mode": self.__aggregation_mode, "central_node": self.__central_node}


@app.route("/")
@error_handler
def home():
    return jsonify({"Message": "Oracle up and running"})


@app.route("/faucet", methods=["POST"])
@error_handler
def rest_transfer_funds():
    address = request.get_json().get("address")
    return jsonify({"Message": oracle.transfer_funds(address)})


@app.route("/gas", methods=["POST"])
@error_handler
def rest_report_gas():
    amount = request.get_json().get("amount")
    aggregation_round = request.get_json().get("round")
    oracle.report_gas(amount, aggregation_round)
    return jsonify(oracle.get_gas_report())


@app.route("/balance", methods=["GET"])
@error_handler
def rest_get_balance():
    addr = request.get_json().get("address")
    return jsonify(oracle.get_balance(addr))


@app.route("/status", methods=["GET"])
@error_handler
def rest_status():
    if not oracle.ready:
        return {"message": "Blockchain does not respond, wait 10"}
    else:
        return {"message": "Blockchain responded"}


@app.route("/contract", methods=["GET"])
@error_handler
def rest_contract():
    return jsonify({"address": oracle.contract_address, "abi": oracle.contract_abi})


@app.route("/gas", methods=["GET"])
@error_handler
def rest_get_gas_report():
    return oracle.get_gas_report()


@app.route("/gas_series", methods=["GET"])
@error_handler
def rest_get_gas_series():
    return oracle.gas_store


@app.route("/time", methods=["POST"])
@error_handler
def rest_report_time():
    time = request.get_json().get("time")
    aggregation_round = request.get_json().get("round")
    oracle.report_time(time, aggregation_round)
    return jsonify({"Message": "Reported time successfully"})


@app.route("/time", methods=["GET"])
@error_handler
def rest_get_time_report():
    return oracle.time_store


@app.route("/reputation", methods=["POST"])
@error_handler
def rest_report_reputation():
    records = request.get_json().get("records")
    round = request.get_json().get("round")
    sender = request.get_json().get("sender")
    oracle.report_reputation(records, round, sender)
    return jsonify({"Message": "Reported reputation successfully"})


@app.route("/reputation", methods=["GET"])
@error_handler
def rest_get_reputation_timeseries():
    return oracle.reputation_store


@app.route("/client_status", methods=["GET"])
@error_handler
def rest_get_client_status():
    logging.info("Client status request received")
    logging.info(f"Current client status: {oracle.get_all_client_status()}")
    return jsonify(oracle.get_all_client_status())


@app.route("/client_status", methods=["POST"])
@error_handler
def rest_report_client_status():
    status_data = request.get_json()
    logging.info(f"Received status update: {status_data}")
    response = oracle.update_client_status(status_data)
    return jsonify({"Message": "Client status updated", "data": response})


@app.route("/active_clients", methods=["GET"])
@error_handler
def rest_get_active_clients():
    return jsonify(oracle.get_active_clients())


@app.route("/select_clients", methods=["GET"])
@error_handler
def rest_select_clients():
    num_clients = request.args.get("num_clients", type=int)
    criteria = request.args.get("criteria", "random")
    selected = oracle.select_clients(num_clients, criteria)
    return jsonify(selected)


@app.route("/model/version", methods=["POST"])
@error_handler
def register_model_version():
    data = request.get_json()
    return jsonify(oracle.register_model_version(data))


@app.route("/model/versions/<client_id>", methods=["GET"])
@error_handler
def get_model_versions(client_id):
    return jsonify(oracle.get_model_versions(client_id))


@app.route("/model/performance", methods=["POST"])
@error_handler
def check_performance():
    data = request.get_json()
    needs_replacement = oracle.check_model_performance(data["client_id"], data["performance"])
    if needs_replacement:
        return jsonify(oracle.trigger_model_replacement(data["client_id"]))
    return jsonify({"replace_model": False})


@app.route("/model/state/<version>", methods=["GET"])
@error_handler
def get_model_state(version):
    return jsonify(oracle.get_model_state(version))


@app.route("/model/state", methods=["POST"])
@error_handler
def update_model_state():
    data = request.get_json()
    return jsonify(oracle.update_model_state(data))


@app.route("/optimization/benchmark", methods=["POST"])
@error_handler
def store_benchmark():
    data = request.get_json()
    return jsonify(oracle.store_benchmark_data(data["client_id"], data["metrics"]))


@app.route("/optimization/history/<client_id>", methods=["GET"])
@error_handler
def get_optimization_history(client_id):
    return jsonify(oracle.get_optimization_history(client_id))


@app.route("/mode", methods=["POST"])
@error_handler
def update_mode():
    data = request.get_json()
    return jsonify(oracle.update_aggregation_mode(data))


@app.route("/mode", methods=["GET"])
@error_handler
def get_mode():
    return jsonify({
        "mode": oracle._Oracle__aggregation_mode,  # Access private attribute properly
        "central_node": oracle._Oracle__central_node,
        "history": oracle._Oracle__mode_history,
    })


if __name__ == "__main__":
    oracle = Oracle()
    app.run(debug=False, host="0.0.0.0", port=8081)
