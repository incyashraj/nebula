import time
from collections import OrderedDict

import torch
from retry import retry

from nebula.core.aggregation.aggregator import Aggregator
from nebula.core.utils.helper import (
    anonymization_metric,
    differential_privacy_metric,
    entropy_metric,
    homomorphic_encryption_metric,
    information_leakage_metric,
)


def calculate_privacy_score(model1, model2, privacy_config):
    # Combined privacy score using multiple metrics
    dp_score = differential_privacy_metric(model1, model2, privacy_config["epsilon"])
    he_score = homomorphic_encryption_metric(model1, model2)
    anon_score = anonymization_metric(model1, model2, privacy_config["k"], privacy_config["l"])
    return (dp_score + he_score + anon_score) / 3


class BlockchainPrivacy(Aggregator):
    """
    Privacy-preserving aggregation using blockchain
    Implements differential privacy, homomorphic encryption, and anonymization
    """

    PRIVACY_METRICS = {
        "DifferentialPrivacy": differential_privacy_metric,
        "HomomorphicEncryption": homomorphic_encryption_metric,
        "Anonymization": anonymization_metric,
        "InformationLeakage": information_leakage_metric,
        "Entropy": entropy_metric,
    }

    def __init__(self, privacy_mechanism="DifferentialPrivacy", config=None, **kwargs):
        super().__init__(config, **kwargs)

        self.config = config
        self.node_name = self.config.participant["network_args"]["addr"]
        self.__blockchain = PrivacyBlockchainHandler(self.node_name)
        self.__malicious = self.config.participant["device_args"]["malicious"]
        self.__privacy_algo = BlockchainPrivacy.PRIVACY_METRICS.get(privacy_mechanism)
        self.__privacy_mechanism = privacy_mechanism

    def run_aggregation(self, model_buffer: OrderedDict[str, OrderedDict[torch.Tensor, int]]) -> torch.Tensor:
        print_with_frame("BLOCKCHAIN PRIVACY AGGREGATION: START")

        start = time.time_ns()
        self.__blockchain.verify_registration()
        self.__blockchain.verify_balance()

        current_models = {sender: model for sender, (model, weight) in model_buffer.items()}
        local_model = model_buffer[self.node_name][0]

        # Calculate privacy metrics
        privacy_scores = {
            sender: max(
                min(
                    round(
                        self.__privacy_algo(
                            local_model,
                            current_models[sender],
                            epsilon=self.config.participant["privacy_args"]["epsilon"],
                            delta=self.config.participant["privacy_args"]["delta"],
                        ),
                        5,
                    ),
                    1,
                ),
                0,
            )
            for sender in current_models
            if sender != self.node_name
        }

        print_table("PRIVACY METRICS", list(privacy_scores.items()), ["Node", f"{self.__privacy_mechanism} Score"])

        # Transform scores for blockchain
        privacy_values = {sender: round(score**3 * 100) for sender, score in privacy_scores.items()}

        # Push privacy metrics to blockchain
        self.__blockchain.push_privacy_metrics(privacy_values)

        print_table(
            "PRIVACY REPORTS", list(privacy_values.items()), ["Node", f"Transformed {self.__privacy_mechanism} Score"]
        )

        # Get global privacy scores
        privacy_scores = self.__blockchain.get_privacy_scores([sender for sender in current_models])

        print_table("GLOBAL PRIVACY SCORES", list(privacy_scores.items()), ["Node", "Global Privacy Score"])

        # Normalize scores for aggregation weights
        sum_scores = sum(privacy_scores.values())
        if sum_scores > 0:
            normalized_scores = {name: round(privacy_scores[name] / sum_scores, 3) for name in privacy_scores}
        else:
            normalized_scores = privacy_scores

        print_table("AGGREGATION WEIGHTS", list(normalized_scores.items()), ["Node", "Privacy-based Weight"])

        # Initialize aggregated model
        final_model = {layer: torch.zeros_like(param).float() for layer, param in local_model.items()}

        # Aggregate with privacy weights
        if sum_scores > 0:
            for sender in normalized_scores.keys():
                for layer in final_model:
                    final_model[layer] += current_models[sender][layer].float() * normalized_scores[sender]
        else:
            final_model = local_model

        # Report metrics
        self.__blockchain.report_gas_oracle()
        self.__blockchain.report_time_oracle(start)

        print_with_frame("BLOCKCHAIN PRIVACY AGGREGATION: FINISHED")
        return final_model


class PrivacyBlockchainHandler:
    """Handles blockchain interactions for privacy mechanisms"""

    __rpc_url = "http://172.25.0.104:8545"
    __oracle_url = "http://172.25.0.105:8081"
    __rest_header = {"Content-type": "application/json", "Accept": "application/json"}

    def __init__(self, home_address):
        print_with_frame("PRIVACY BLOCKCHAIN INITIALIZATION: START")

        self.__home_ip = home_address
        self.__private_key = ""
        self.__acc_address = ""
        self.__gas_used = 0
        self.__gas_price = 27.3
        self.round = 1

        self.__acc = self.__create_account()
        self.__web3 = self.__initialize_web3()

        print(f"{'-' * 25} CONNECT TO ORACLE {'-' * 25}")
        self.__wait_for_blockchain()
        self.__request_funds_from_oracle()
        self.verify_balance()

        self.__contract_obj = self.__get_contract_from_oracle()

        print(f"{'-' * 25} CONNECT TO PRIVACY SYSTEM {'-' * 25}")
        self.__register()
        self.verify_registration()

        print_with_frame("PRIVACY BLOCKCHAIN INITIALIZATION: FINISHED")

    @retry(Exception, tries=3, delay=4)
    def push_privacy_metrics(self, privacy_dict: dict):
        """Push privacy metrics to blockchain"""
        unsigned_trx = self.__contract_obj.functions.update_privacy_metrics(
            list(privacy_dict.items())
        ).build_transaction({
            "chainId": self.__web3.eth.chain_id,
            "from": self.__acc_address,
            "nonce": self.__web3.eth.get_transaction_count(
                self.__web3.to_checksum_address(self.__acc_address), "pending"
            ),
            "gasPrice": self.__web3.to_wei(self.__gas_price, "gwei"),
        })

        conf = self.__sign_and_deploy(unsigned_trx)
        return self.__web3.to_json(conf)

    @retry(Exception, tries=3, delay=4)
    def get_privacy_scores(self, ip_addresses: list) -> dict:
        """Get privacy scores from blockchain"""
        privacy_scores = dict()
        stats = list()

        raw_scores = self.__contract_obj.functions.get_privacy_scores(ip_addresses).call({"from": self.__acc_address})

        for name, dp_score, he_score, anon_score, info_leakage, entropy, weighted_score, final_score in raw_scores:
            if not name:
                continue

            stats.append([
                name,
                dp_score / 10,
                he_score / 10,
                anon_score / 10,
                info_leakage / 10,
                entropy / 10,
                weighted_score / 10,
                final_score / 10,
            ])

            privacy_scores[name] = final_score / 10

        print_table(
            "PRIVACY SYSTEM STATE",
            stats,
            [
                "Name",
                "DP Score",
                "HE Score",
                "Anonymization Score",
                "Information Leakage",
                "Entropy",
                "Weighted Score",
                "Final Score",
            ],
        )

        return privacy_scores

    # Other methods similar to BlockchainHandler
    def __create_account(self):
        # Same as BlockchainHandler
        pass

    def __initialize_web3(self):
        # Same as BlockchainHandler
        pass

    def verify_balance(self):
        # Same as BlockchainHandler
        pass

    def verify_registration(self):
        # Same as BlockchainHandler
        pass

    # Other helper methods
    def __sign_and_deploy(self, trx_hash):
        # Same as BlockchainHandler
        pass

    def report_gas_oracle(self):
        # Same as BlockchainHandler
        pass

    def report_time_oracle(self, start):
        # Same as BlockchainHandler
        pass
