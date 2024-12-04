[1mdiff --git a/nebula/addons/blockchain/oracle/app.py b/nebula/addons/blockchain/oracle/app.py[m
[1mindex abe567f..3344df7 100755[m
[1m--- a/nebula/addons/blockchain/oracle/app.py[m
[1m+++ b/nebula/addons/blockchain/oracle/app.py[m
[36m@@ -1,10 +1,10 @@[m
 import json[m
[32m+[m[32mimport logging[m
 import os[m
[32m+[m[32mimport random[m
 from collections.abc import Mapping[m
[31m-from functools import wraps[m
 from datetime import datetime[m
[31m-import logging[m
[31m-import random[m
[32m+[m[32mfrom functools import wraps[m
 [m
 import requests[m
 from eth_account import Account[m
[36m@@ -72,7 +72,7 @@[m [mclass Oracle:[m
         self.__inactive_timeout = 600  # 60 seconds timeout[m
 [m
         self.__model_registry = {}  # Store model versions[m
[31m-        self.__global_version = 0   # Track global model version[m
[32m+[m[32m        self.__global_version = 0  # Track global model version[m
 [m
         self.__performance_threshold = 0.8[m
         self.__performance_history = {}[m
[36m@@ -81,9 +81,9 @@[m [mclass Oracle:[m
 [m
         self.__benchmark_data = {}[m
         self.__optimization_thresholds = {[m
[31m-            'convergence_rate': 0.001,  # Minimum improvement rate[m
[31m-            'communication_overhead': 1000,  # Maximum bytes[m
[31m-            'aggregation_time': 60  # Maximum seconds[m
[32m+[m[32m            "convergence_rate": 0.001,  # Minimum improvement rate[m
[32m+[m[32m            "communication_overhead": 1000,  # Maximum bytes[m
[32m+[m[32m            "aggregation_time": 60,  # Maximum seconds[m
         }[m
 [m
         # create a Web3 contract object from the compiled chaincode[m
[36m@@ -403,17 +403,19 @@[m [mclass Oracle:[m
 [m
         """[m
         return self.__ready[m
[31m-    [m
[32m+[m
     def is_client_active(self, last_seen_str):[m
         """Check if client is still active based on last_seen time"""[m
         try:[m
             last_seen = datetime.fromisoformat(last_seen_str)[m
             time_since_update = (datetime.now() - last_seen).total_seconds()[m
             is_active = time_since_update < self.__inactive_timeout[m
[31m-            logging.info(f"Checking active status: last_seen={last_seen_str}, time_since_update={time_since_update}, timeout={self.__inactive_timeout}, is_active={is_active}")[m
[32m+[m[32m            logging.info([m
[32m+[m[32m                f"Checking active status: last_seen={last_seen_str}, time_since_update={time_since_update}, timeout={self.__inactive_timeout}, is_active={is_active}"[m
[32m+[m[32m            )[m
             return is_active[m
         except Exception as e:[m
[31m-            logging.error(f"Error checking client active status: {e}")[m
[32m+[m[32m            logging.exception(f"Error checking client active status: {e}")[m
             return False[m
 [m
     def update_client_status(self, status_data):[m
[36m@@ -423,22 +425,24 @@[m [mclass Oracle:[m
             current_time = datetime.now()[m
             last_seen = datetime.fromisoformat(status_data["last_seen"])[m
             time_since_update = (current_time - last_seen).total_seconds()[m
[31m-        [m
[32m+[m
             # Mark active if seen in last 5 minutes[m
             status_data["active"] = time_since_update < self.__inactive_timeout[m
             if status_data["active"]:[m
                 self.__active_clients.add(client_id)[m
             else:[m
                 self.__active_clients.discard(client_id)[m
[31m-            [m
[32m+[m
             self.__client_status[client_id] = status_data[m
[31m-        [m
[31m-            print(f"Client {client_id}: last_seen={last_seen}, time_since={time_since_update}s, active={status_data['active']}")[m
[31m-        [m
[32m+[m
[32m+[m[32m            print([m
[32m+[m[32m                f"Client {client_id}: last_seen={last_seen}, time_since={time_since_update}s, active={status_data['active']}"[m
[32m+[m[32m            )[m
[32m+[m
             return {[m
                 "total_clients": len(self.__client_status),[m
                 "active_clients": len(self.__active_clients),[m
[31m-                "time_since_update": time_since_update[m
[32m+[m[32m                "time_since_update": time_since_update,[m
             }[m
         except Exception as e:[m
             print(f"Error updating client status: {e}")[m
[36m@@ -458,20 +462,20 @@[m [mclass Oracle:[m
                 status["active"] = True[m
                 self.__active_clients.add(client_id)[m
         return self.__client_status[m
[31m-    [m
[32m+[m
     def select_clients(self, num_clients=None, selection_criteria="random"):[m
         """Select eligible clients for training round"""[m
         active_clients = list(self.__active_clients)[m
[31m-    [m
[32m+[m
         if not active_clients:[m
             return [][m
[31m-    [m
[32m+[m
         if not num_clients:[m
             num_clients = len(active_clients)[m
[31m-    [m
[32m+[m
         # Get latest statuses[m
         client_statuses = self.get_all_client_status()[m
[31m-    [m
[32m+[m
         # Filter based on criteria[m
         eligible_clients = [][m
         for client in active_clients:[m
[36m@@ -479,18 +483,17 @@[m [mclass Oracle:[m
             # Basic eligibility checks[m
             if status.get("active") and status.get("uptime_seconds", 0) > 30:[m
                 eligible_clients.append(client)[m
[31m-    [m
[32m+[m
         # Select clients based on strategy[m
         if selection_criteria == "random":[m
             return random.sample(eligible_clients, min(num_clients, len(eligible_clients)))[m
         elif selection_criteria == "reputation":[m
             # Sort by gas usage as simple reputation metric[m
[31m-            sorted_clients = sorted(eligible_clients, [m
[31m-                                  key=lambda x: client_statuses[x].get("gas_used", 0))[m
[32m+[m[32m            sorted_clients = sorted(eligible_clients, key=lambda x: client_statuses[x].get("gas_used", 0))[m
             return sorted_clients[:num_clients][m
[31m-        [m
[32m+[m
         return eligible_clients[:num_clients][m
[31m-    [m
[32m+[m
     def register_model_version(self, data):[m
         """[m
         Register a model version[m
[36m@@ -502,29 +505,26 @@[m [mclass Oracle:[m
             'performance': float[m
         }[m
         """[m
[31m-        client_id = data['client_id'][m
[32m+[m[32m        client_id = data["client_id"][m
         if client_id not in self.__model_registry:[m
             self.__model_registry[client_id] = [][m
         self.__model_registry[client_id].append(data)[m
         return {"status": "success", "global_version": self.__global_version}[m
[31m-    [m
[32m+[m
     def get_model_versions(self, client_id):[m
[31m-        return {[m
[31m-            'versions': self.__model_registry.get(client_id, []),[m
[31m-            'current_global': self.__global_version[m
[31m-        }[m
[32m+[m[32m        return {"versions": self.__model_registry.get(client_id, []), "current_global": self.__global_version}[m
 [m
     def update_global_version(self):[m
         self.__global_version += 1[m
         return self.__global_version[m
[31m-    [m
[32m+[m
     def check_model_performance(self, client_id, performance):[m
         """Monitor model performance and detect degradation"""[m
         if client_id not in self.__performance_history:[m
             self.__performance_history[client_id] = [][m
[31m-            [m
[32m+[m
         self.__performance_history[client_id].append(performance)[m
[31m-        [m
[32m+[m
         # Check for degradation[m
         if len(self.__performance_history[client_id]) >= 3:[m
             recent = self.__performance_history[client_id][-3:][m
[36m@@ -537,36 +537,36 @@[m [mclass Oracle:[m
         logging.info(f"Triggering model replacement for {client_id}")[m
         self.__global_version += 1[m
         return {"new_version": self.__global_version}[m
[31m-    [m
[32m+[m
     def get_latest_model_version(self):[m
         """Get latest model state"""[m
         return {[m
[31m-            'version': self.__global_version,[m
[31m-            'performance_threshold': self.__performance_threshold,[m
[31m-            'active_clients': len(self.__active_clients)[m
[32m+[m[32m            "version": self.__global_version,[m
[32m+[m[32m            "performance_threshold": self.__performance_threshold,[m
[32m+[m[32m            "active_clients": len(self.__active_clients),[m
         }[m
[31m-    [m
[32m+[m
     def get_model_state(self, version):[m
         return self.__model_states.get(str(version))[m
 [m
     def update_model_state(self, data):[m
[31m-        version = str(data['version'])[m
[31m-        self.__model_states[version] = data['state'][m
[31m-        return {'version': version}[m
[32m+[m[32m        version = str(data["version"])[m
[32m+[m[32m        self.__model_states[version] = data["state"][m
[32m+[m[32m        return {"version": version}[m
 [m
     def handle_model_update(self, client_id, model_state, performance):[m
         """Handle model update with version control"""[m
         needs_replacement = self.check_model_performance(client_id, performance)[m
         if needs_replacement:[m
             new_version = self.trigger_model_replacement(client_id)[m
[31m-            self.update_model_state({'version': new_version, 'state': model_state})[m
[32m+[m[32m            self.update_model_state({"version": new_version, "state": model_state})[m
 [m
     def store_benchmark_data(self, client_id, data):[m
         """Store benchmark data from clients"""[m
         if client_id not in self.__benchmark_data:[m
             self.__benchmark_data[client_id] = [][m
         self.__benchmark_data[client_id].append(data)[m
[31m-        [m
[32m+[m
         return self.optimize_parameters(client_id)[m
 [m
     def optimize_parameters(self, client_id):[m
[36m@@ -575,46 +575,44 @@[m [mclass Oracle:[m
             return {}[m
 [m
         recent_data = self.__benchmark_data[client_id][-5:]  # Last 5 rounds[m
[31m-        [m
[32m+[m
         # Calculate optimization metrics[m
[31m-        avg_convergence = sum(d['convergence_rate'] for d in recent_data) / len(recent_data)[m
[31m-        avg_overhead = sum(d['communication_overhead'] for d in recent_data) / len(recent_data)[m
[31m-        [m
[32m+[m[32m        avg_convergence = sum(d["convergence_rate"] for d in recent_data) / len(recent_data)[m
[32m+[m[32m        avg_overhead = sum(d["communication_overhead"] for d in recent_data) / len(recent_data)[m
[32m+[m
         # Return optimization suggestions[m
         return {[m
[31m-            'optimize_batch_size': avg_overhead > self.__optimization_thresholds['communication_overhead'],[m
[31m-            'adjust_learning_rate': avg_convergence < self.__optimization_thresholds['convergence_rate'][m
[32m+[m[32m            "optimize_batch_size": avg_overhead > self.__optimization_thresholds["communication_overhead"],[m
[32m+[m[32m            "adjust_learning_rate": avg_convergence < self.__optimization_thresholds["convergence_rate"],[m
         }[m
[31m-    [m
[32m+[m
     def get_optimization_history(self, client_id):[m
         """Get optimization history for a client"""[m
         return {[m
[31m-            'benchmark_data': self.__benchmark_data.get(client_id, []),[m
[31m-            'optimization_thresholds': self.__optimization_thresholds,[m
[31m-            'total_optimizations': len(self.__benchmark_data.get(client_id, []))[m
[32m+[m[32m            "benchmark_data": self.__benchmark_data.get(client_id, []),[m
[32m+[m[32m            "optimization_thresholds": self.__optimization_thresholds,[m
[32m+[m[32m            "total_optimizations": len(self.__benchmark_data.get(client_id, [])),[m
         }[m
[31m-    [m
[32m+[m
     def update_aggregation_mode(self, data):[m
         """Update system aggregation mode"""[m
[31m-        mode = data.get('mode')[m
[31m-        central_node = data.get('central_node')[m
[31m-        [m
[32m+[m[32m        mode = data.get("mode")[m
[32m+[m[32m        central_node = data.get("central_node")[m
[32m+[m
         if mode not in ["centralized", "decentralized"]:[m
             return {"error": "Invalid mode"}[m
[31m-            [m
[32m+[m
         self.__aggregation_mode = mode[m
         self.__central_node = central_node if mode == "centralized" else None[m
[31m-        [m
[32m+[m
         self.__mode_history.append({[m
[31m-            'timestamp': datetime.now().isoformat(),[m
[31m-            'mode': mode,[m
[31m-            'central_node': central_node[m
[32m+[m[32m            "timestamp": datetime.now().isoformat(),[m
[32m+[m[32m            "mode": mode,[m
[32m+[m[32m            "central_node": central_node,[m
         })[m
[31m-        [m
[31m-        return {[m
[31m-            'mode': self.__aggregation_mode,[m
[31m-            'central_node': self.__central_node[m
[31m-        }[m
[32m+[m
[32m+[m[32m        return {"mode": self.__aggregation_mode, "central_node": self.__central_node}[m
[32m+[m
 [m
 @app.route("/")[m
 @error_handler[m
[36m@@ -702,6 +700,7 @@[m [mdef rest_report_reputation():[m
 def rest_get_reputation_timeseries():[m
     return oracle.reputation_store[m
 [m
[32m+[m
 @app.route("/client_status", methods=["GET"])[m
 @error_handler[m
 def rest_get_client_status():[m
[36m@@ -709,6 +708,7 @@[m [mdef rest_get_client_status():[m
     logging.info(f"Current client status: {oracle.get_all_client_status()}")[m
     return jsonify(oracle.get_all_client_status())[m
 [m
[32m+[m
 @app.route("/client_status", methods=["POST"])[m
 @error_handler[m
 def rest_report_client_status():[m
[36m@@ -717,11 +717,13 @@[m [mdef rest_report_client_status():[m
     response = oracle.update_client_status(status_data)[m
     return jsonify({"Message": "Client status updated", "data": response})[m
 [m
[32m+[m
 @app.route("/active_clients", methods=["GET"])[m
 @error_handler[m
 def rest_get_active_clients():[m
     return jsonify(oracle.get_active_clients())[m
 [m
[32m+[m
 @app.route("/select_clients", methods=["GET"])[m
 @error_handler[m
 def rest_select_clients():[m
[36m@@ -730,64 +732,70 @@[m [mdef rest_select_clients():[m
     selected = oracle.select_clients(num_clients, criteria)[m
     return jsonify(selected)[m
 [m
[32m+[m
 @app.route("/model/version", methods=["POST"])[m
 @error_handler[m
 def register_model_version():[m
     data = request.get_json()[m
     return jsonify(oracle.register_model_version(data))[m
 [m
[32m+[m
 @app.route("/model/versions/<client_id>", methods=["GET"])[m
 @error_handler[m
 def get_model_versions(client_id):[m
     return jsonify(oracle.get_model_versions(client_id))[m
 [m
[32m+[m
 @app.route("/model/performance", methods=["POST"])[m
 @error_handler[m
 def check_performance():[m
     data = request.get_json()[m
[31m-    needs_replacement = oracle.check_model_performance([m
[31m-        data['client_id'], [m
[31m-        data['performance'][m
[31m-    )[m
[32m+[m[32m    needs_replacement = oracle.check_model_performance(data["client_id"], data["performance"])[m
     if needs_replacement:[m
[31m-        return jsonify(oracle.trigger_model_replacement(data['client_id']))[m
[31m-    return jsonify({'replace_model': False})[m
[32m+[m[32m        return jsonify(oracle.trigger_model_replacement(data["client_id"]))[m
[32m+[m[32m    return jsonify({"replace_model": False})[m
[32m+[m
 [m
 @app.route("/model/state/<version>", methods=["GET"])[m
 @error_handler[m
 def get_model_state(version):[m
     return jsonify(oracle.get_model_state(version))[m
 [m
[32m+[m
 @app.route("/model/state", methods=["POST"])[m
 @error_handler[m
 def update_model_state():[m
     data = request.get_json()[m
     return jsonify(oracle.update_model_state(data))[m
 [m
[32m+[m
 @app.route("/optimization/benchmark", methods=["POST"])[m
 @error_handler[m
 def store_benchmark():[m
     data = request.get_json()[m
[31m-    return jsonify(oracle.store_benchmark_data(data['client_id'], data['metrics']))[m
[32m+[m[32m    return jsonify(oracle.store_benchmark_data(data["client_id"], data["metrics"]))[m
[32m+[m
 [m
 @app.route("/optimization/history/<client_id>", methods=["GET"])[m
 @error_handler[m
 def get_optimization_history(client_id):[m
     return jsonify(oracle.get_optimization_history(client_id))[m
 [m
[32m+[m
 @app.route("/mode", methods=["POST"])[m
 @error_handler[m
 def update_mode():[m
     data = request.get_json()[m
     return jsonify(oracle.update_aggregation_mode(data))[m
 [m
[32m+[m
 @app.route("/mode", methods=["GET"])[m
 @error_handler[m
 def get_mode():[m
     return jsonify({[m
[31m-        'mode': oracle._Oracle__aggregation_mode,  # Access private attribute properly [m
[31m-        'central_node': oracle._Oracle__central_node,[m
[31m-        'history': oracle._Oracle__mode_history[m
[32m+[m[32m        "mode": oracle._Oracle__aggregation_mode,  # Access private attribute properly[m
[32m+[m[32m        "central_node": oracle._Oracle__central_node,[m
[32m+[m[32m        "history": oracle._Oracle__mode_history,[m
     })[m
 [m
 [m
[1mdiff --git a/nebula/core/aggregation/blockchainPrivacy.py b/nebula/core/aggregation/blockchainPrivacy.py[m
[1mindex 31f7368..b46e64b 100644[m
[1m--- a/nebula/core/aggregation/blockchainPrivacy.py[m
[1m+++ b/nebula/core/aggregation/blockchainPrivacy.py[m
[36m@@ -1,22 +1,19 @@[m
 import time[m
 from collections import OrderedDict[m
[32m+[m
 import torch[m
[31m-from web3 import Web3[m
[31m-from web3.middleware import construct_sign_and_send_raw_middleware, geth_poa_middleware[m
[31m-from eth_account import Account[m
[31m-import requests[m
[31m-from tabulate import tabulate[m
 from retry import retry[m
 [m
 from nebula.core.aggregation.aggregator import Aggregator[m
 from nebula.core.utils.helper import ([m
[32m+[m[32m    anonymization_metric,[m
     differential_privacy_metric,[m
[32m+[m[32m    entropy_metric,[m
     homomorphic_encryption_metric,[m
[31m-    anonymization_metric,[m
     information_leakage_metric,[m
[31m-    entropy_metric[m
 )[m
 [m
[32m+[m
 def calculate_privacy_score(model1, model2, privacy_config):[m
     # Combined privacy score using multiple metrics[m
     dp_score = differential_privacy_metric(model1, model2, privacy_config["epsilon"])[m
[36m@@ -24,23 +21,24 @@[m [mdef calculate_privacy_score(model1, model2, privacy_config):[m
     anon_score = anonymization_metric(model1, model2, privacy_config["k"], privacy_config["l"])[m
     return (dp_score + he_score + anon_score) / 3[m
 [m
[32m+[m
 class BlockchainPrivacy(Aggregator):[m
     """[m
     Privacy-preserving aggregation using blockchain[m
     Implements differential privacy, homomorphic encryption, and anonymization[m
     """[m
[31m-    [m
[32m+[m
     PRIVACY_METRICS = {[m
         "DifferentialPrivacy": differential_privacy_metric,[m
         "HomomorphicEncryption": homomorphic_encryption_metric,[m
         "Anonymization": anonymization_metric,[m
         "InformationLeakage": information_leakage_metric,[m
[31m-        "Entropy": entropy_metric[m
[32m+[m[32m        "Entropy": entropy_metric,[m
     }[m
 [m
     def __init__(self, privacy_mechanism="DifferentialPrivacy", config=None, **kwargs):[m
         super().__init__(config, **kwargs)[m
[31m-        [m
[32m+[m
         self.config = config[m
         self.node_name = self.config.participant["network_args"]["addr"][m
         self.__blockchain = PrivacyBlockchainHandler(self.node_name)[m
[36m@@ -50,7 +48,7 @@[m [mclass BlockchainPrivacy(Aggregator):[m
 [m
     def run_aggregation(self, model_buffer: OrderedDict[str, OrderedDict[torch.Tensor, int]]) -> torch.Tensor:[m
         print_with_frame("BLOCKCHAIN PRIVACY AGGREGATION: START")[m
[31m-        [m
[32m+[m
         start = time.time_ns()[m
         self.__blockchain.verify_registration()[m
         self.__blockchain.verify_balance()[m
[36m@@ -64,74 +62,49 @@[m [mclass BlockchainPrivacy(Aggregator):[m
                 min([m
                     round([m
                         self.__privacy_algo([m
[31m-                            local_model, [m
[32m+[m[32m                            local_model,[m
                             current_models[sender],[m
                             epsilon=self.config.participant["privacy_args"]["epsilon"],[m
[31m-                            delta=self.config.participant["privacy_args"]["delta"][m
[32m+[m[32m                            delta=self.config.participant["privacy_args"]["delta"],[m
                         ),[m
[31m-                        5[m
[32m+[m[32m                        5,[m
                     ),[m
[31m-                    1[m
[32m+[m[32m                    1,[m
                 ),[m
[31m-                0[m
[32m+[m[32m                0,[m
             )[m
             for sender in current_models[m
             if sender != self.node_name[m
         }[m
 [m
[31m-        print_table([m
[31m-            "PRIVACY METRICS",[m
[31m-            list(privacy_scores.items()),[m
[31m-            ["Node", f"{self.__privacy_mechanism} Score"][m
[31m-        )[m
[32m+[m[32m        print_table("PRIVACY METRICS", list(privacy_scores.items()), ["Node", f"{self.__privacy_mechanism} Score"])[m
 [m
         # Transform scores for blockchain[m
[31m-        privacy_values = {[m
[31m-            sender: round(score**3 * 100) [m
[31m-            for sender, score in privacy_scores.items()[m
[31m-        }[m
[32m+[m[32m        privacy_values = {sender: round(score**3 * 100) for sender, score in privacy_scores.items()}[m
 [m
         # Push privacy metrics to blockchain[m
         self.__blockchain.push_privacy_metrics(privacy_values)[m
 [m
         print_table([m
[31m-            "PRIVACY REPORTS",[m
[31m-            list(privacy_values.items()),[m
[31m-            ["Node", f"Transformed {self.__privacy_mechanism} Score"][m
[32m+[m[32m            "PRIVACY REPORTS", list(privacy_values.items()), ["Node", f"Transformed {self.__privacy_mechanism} Score"][m
         )[m
 [m
         # Get global privacy scores[m
[31m-        privacy_scores = self.__blockchain.get_privacy_scores([m
[31m-            [sender for sender in current_models][m
[31m-        )[m
[32m+[m[32m        privacy_scores = self.__blockchain.get_privacy_scores([sender for sender in current_models])[m
 [m
[31m-        print_table([m
[31m-            "GLOBAL PRIVACY SCORES",[m
[31m-            list(privacy_scores.items()),[m
[31m-            ["Node", "Global Privacy Score"][m
[31m-        )[m
[32m+[m[32m        print_table("GLOBAL PRIVACY SCORES", list(privacy_scores.items()), ["Node", "Global Privacy Score"])[m
 [m
         # Normalize scores for aggregation weights[m
         sum_scores = sum(privacy_scores.values())[m
         if sum_scores > 0:[m
[31m-            normalized_scores = {[m
[31m-                name: round(privacy_scores[name] / sum_scores, 3)[m
[31m-                for name in privacy_scores[m
[31m-            }[m
[32m+[m[32m            normalized_scores = {name: round(privacy_scores[name] / sum_scores, 3) for name in privacy_scores}[m
         else:[m
             normalized_scores = privacy_scores[m
 [m
[31m-        print_table([m
[31m-            "AGGREGATION WEIGHTS",[m
[31m-            list(normalized_scores.items()),[m
[31m-            ["Node", "Privacy-based Weight"][m
[31m-        )[m
[32m+[m[32m        print_table("AGGREGATION WEIGHTS", list(normalized_scores.items()), ["Node", "Privacy-based Weight"])[m
 [m
         # Initialize aggregated model[m
[31m-        final_model = {[m
[31m-            layer: torch.zeros_like(param).float() [m
[31m-            for layer, param in local_model.items()[m
[31m-        }[m
[32m+[m[32m        final_model = {layer: torch.zeros_like(param).float() for layer, param in local_model.items()}[m
 [m
         # Aggregate with privacy weights[m
         if sum_scores > 0:[m
[36m@@ -145,22 +118,20 @@[m [mclass BlockchainPrivacy(Aggregator):[m
         self.__blockchain.report_gas_oracle()[m
         self.__blockchain.report_time_oracle(start)[m
 [m
[31m-        print_with_frame("BLOCKCHAIN PRIVACY AGGREGATION: FINISHED") [m
[32m+[m[32m        print_with_frame("BLOCKCHAIN PRIVACY AGGREGATION: FINISHED")[m
         return final_model[m
[31m-    [m
[32m+[m
[32m+[m
 class PrivacyBlockchainHandler:[m
     """Handles blockchain interactions for privacy mechanisms"""[m
[31m-    [m
[32m+[m
     __rpc_url = "http://172.25.0.104:8545"[m
     __oracle_url = "http://172.25.0.105:8081"[m
[31m-    __rest_header = {[m
[31m-        "Content-type": "application/json",[m
[31m-        "Accept": "application/json"[m
[31m-    }[m
[32m+[m[32m    __rest_header = {"Content-type": "application/json", "Accept": "application/json"}[m
 [m
     def __init__(self, home_address):[m
         print_with_frame("PRIVACY BLOCKCHAIN INITIALIZATION: START")[m
[31m-        [m
[32m+[m
         self.__home_ip = home_address[m
         self.__private_key = ""[m
         self.__acc_address = ""[m
[36m@@ -170,18 +141,18 @@[m [mclass PrivacyBlockchainHandler:[m
 [m
         self.__acc = self.__create_account()[m
         self.__web3 = self.__initialize_web3()[m
[31m-        [m
[32m+[m
         print(f"{'-' * 25} CONNECT TO ORACLE {'-' * 25}")[m
         self.__wait_for_blockchain()[m
         self.__request_funds_from_oracle()[m
         self.verify_balance()[m
[31m-        [m
[32m+[m
         self.__contract_obj = self.__get_contract_from_oracle()[m
[31m-        [m
[32m+[m
         print(f"{'-' * 25} CONNECT TO PRIVACY SYSTEM {'-' * 25}")[m
         self.__register()[m
         self.verify_registration()[m
[31m-        [m
[32m+[m
         print_with_frame("PRIVACY BLOCKCHAIN INITIALIZATION: FINISHED")[m
 [m
     @retry(Exception, tries=3, delay=4)[m
[36m@@ -193,12 +164,11 @@[m [mclass PrivacyBlockchainHandler:[m
             "chainId": self.__web3.eth.chain_id,[m
             "from": self.__acc_address,[m
             "nonce": self.__web3.eth.get_transaction_count([m
[31m-                self.__web3.to_checksum_address(self.__acc_address),[m
[31m-                "pending"[m
[32m+[m[32m                self.__web3.to_checksum_address(self.__acc_address), "pending"[m
             ),[m
[31m-            "gasPrice": self.__web3.to_wei(self.__gas_price, "gwei")[m
[32m+[m[32m            "gasPrice": self.__web3.to_wei(self.__gas_price, "gwei"),[m
         })[m
[31m-        [m
[32m+[m
         conf = self.__sign_and_deploy(unsigned_trx)[m
         return self.__web3.to_json(conf)[m
 [m
[36m@@ -207,24 +177,13 @@[m [mclass PrivacyBlockchainHandler:[m
         """Get privacy scores from blockchain"""[m
         privacy_scores = dict()[m
         stats = list()[m
[31m-        [m
[31m-        raw_scores = self.__contract_obj.functions.get_privacy_scores([m
[31m-            ip_addresses[m
[31m-        ).call({"from": self.__acc_address})[m
[31m-        [m
[31m-        for ([m
[31m-            name,[m
[31m-            dp_score,[m
[31m-            he_score, [m
[31m-            anon_score,[m
[31m-            info_leakage,[m
[31m-            entropy,[m
[31m-            weighted_score,[m
[31m-            final_score[m
[31m-        ) in raw_scores:[m
[32m+[m
[32m+[m[32m        raw_scores = self.__contract_obj.functions.get_privacy_scores(ip_addresses).call({"from": self.__acc_address})[m
[32m+[m
[32m+[m[32m        for name, dp_score, he_score, anon_score, info_leakage, entropy, weighted_score, final_score in raw_scores:[m
             if not name:[m
                 continue[m
[31m-                [m
[32m+[m
             stats.append([[m
                 name,[m
                 dp_score / 10,[m
[36m@@ -233,26 +192,26 @@[m [mclass PrivacyBlockchainHandler:[m
                 info_leakage / 10,[m
                 entropy / 10,[m
                 weighted_score / 10,[m
[31m-                final_score / 10[m
[32m+[m[32m                final_score / 10,[m
             ])[m
[31m-            [m
[32m+[m
             privacy_scores[name] = final_score / 10[m
[31m-            [m
[32m+[m
         print_table([m
             "PRIVACY SYSTEM STATE",[m
             stats,[m
             [[m
                 "Name",[m
                 "DP Score",[m
[31m-                "HE Score", [m
[32m+[m[32m                "HE Score",[m
                 "Anonymization Score",[m
                 "Information Leakage",[m
                 "Entropy",[m
                 "Weighted Score",[m
[31m-                "Final Score"[m
[31m-            ][m
[32m+[m[32m                "Final Score",[m
[32m+[m[32m            ],[m
         )[m
[31m-        [m
[32m+[m
         return privacy_scores[m
 [m
     # Other methods similar to BlockchainHandler[m
[36m@@ -283,4 +242,4 @@[m [mclass PrivacyBlockchainHandler:[m
 [m
     def report_time_oracle(self, start):[m
         # Same as BlockchainHandler[m
[31m-        pass[m
\ No newline at end of file[m
[32m+[m[32m        pass[m
[1mdiff --git a/nebula/core/aggregation/blockchainReputation.py b/nebula/core/aggregation/blockchainReputation.py[m
[1mindex 44429b3..f84528c 100755[m
[1m--- a/nebula/core/aggregation/blockchainReputation.py[m
[1m+++ b/nebula/core/aggregation/blockchainReputation.py[m
[36m@@ -1,11 +1,12 @@[m
[32m+[m[32mimport asyncio[m
[32m+[m[32mimport logging[m
 import time[m
 from collections import OrderedDict[m
 from collections.abc import Mapping[m
 from datetime import datetime[m
[32m+[m
 import requests[m
 import torch[m
[31m-import logging[m
[31m-import asyncio[m
 from eth_account import Account[m
 from retry import retry[m
 from tabulate import tabulate[m
[36m@@ -246,21 +247,13 @@[m [mclass BlockchainHandler:[m
         self.__web3 = self.__initialize_web3()[m
 [m
         # Add basic status tracking[m
[31m-        self.status = {[m
[31m-            "active": False,[m
[31m-            "join_time": None,[m
[31m-            "last_seen": None[m
[31m-        }[m
[32m+[m[32m        self.status = {"active": False, "join_time": None, "last_seen": None}[m
 [m
         self.__last_status_update = datetime.now()[m
         self.__status_update_interval = 10  # Status update every 30 seconds[m
         self.__register_periodic_status_update()[m
 [m
[31m-        self.__optimization_metrics = {[m
[31m-            'convergence_rate': 0,[m
[31m-            'communication_overhead': 0,[m
[31m-            'aggregation_time': 0[m
[31m-        }[m
[32m+[m[32m        self.__optimization_metrics = {"convergence_rate": 0, "communication_overhead": 0, "aggregation_time": 0}[m
         self.__benchmark_data = [][m
 [m
         self.__aggregation_mode = "decentralized"  # or "centralized"[m
[36m@@ -675,7 +668,7 @@[m [mclass BlockchainHandler:[m
 [m
             # raise Exception to check again[m
             raise Exception("EXCEPTION: _verify_registration() => Could not be confirmed)")[m
[31m-        [m
[32m+[m
         # Report initial status after successful registration[m
         self.report_status_to_oracle()[m
 [m
[36m@@ -703,27 +696,27 @@[m [mclass BlockchainHandler:[m
         # increase aggregation round counter after reporting time[m
         self.round += 1[m
         return None[m
[31m-    [m
[32m+[m
     def update_status(self):[m
         """Update client's last seen timestamp"""[m
         current_time = datetime.now()[m
         self.status["last_seen"] = current_time[m
         logging.info(f"Status updated - Last seen: {current_time.isoformat()}")[m
[31m-    [m
[32m+[m
     def is_active(self):[m
         """Check if client is still active based on last_seen"""[m
         if not self.status["last_seen"]:[m
             return False[m
         # Consider client inactive if not seen in last 60 seconds[m
         return (datetime.now() - self.status["last_seen"]).total_seconds() < 60[m
[31m-    [m
[32m+[m
     def get_status_report(self):[m
         """Get comprehensive status report for client"""[m
         current_time = datetime.now()[m
         uptime = None[m
         if self.status["join_time"]:[m
             uptime = (current_time - self.status["join_time"]).total_seconds()[m
[31m-    [m
[32m+[m
         return {[m
             "client_id": self.__home_ip,[m
             "active": self.is_active(),[m
[36m@@ -731,26 +724,23 @@[m [mclass BlockchainHandler:[m
             "last_seen": self.status["last_seen"].isoformat() if self.status["last_seen"] else None,[m
             "uptime_seconds": uptime,[m
             "gas_used": self.__gas_used,  # Using existing gas tracking[m
[31m-            "aggregation_round": self.round  # Using existing round tracking[m
[32m+[m[32m            "aggregation_round": self.round,  # Using existing round tracking[m
         }[m
[31m-    [m
[32m+[m
     def report_status_to_oracle(self):[m
         """Report client status to Oracle"""[m
         try:[m
             status_data = self.get_status_report()[m
             logging.info(f"Sending status update to Oracle: {status_data}")[m
             response = requests.post([m
[31m-                url=f"{self.__oracle_url}/client_status",[m
[31m-                json=status_data,[m
[31m-                headers=self.__rest_header,[m
[31m-                timeout=20[m
[32m+[m[32m                url=f"{self.__oracle_url}/client_status", json=status_data, headers=self.__rest_header, timeout=20[m
             )[m
             response.raise_for_status()[m
             return response.json()[m
         except Exception as e:[m
[31m-            logging.error(f"Failed to report status to Oracle: {e}")[m
[32m+[m[32m            logging.exception(f"Failed to report status to Oracle: {e}")[m
             return None[m
[31m-        [m
[32m+[m
     def __should_update_status(self):[m
         """Check if it's time for a status update"""[m
         now = datetime.now()[m
[36m@@ -759,7 +749,7 @@[m [mclass BlockchainHandler:[m
         if should_update:[m
             logging.info(f"Time for status update. Time since last update: {time_since_update}s")[m
         return should_update[m
[31m-    [m
[32m+[m
     def __register_periodic_status_update(self):[m
         """Register the periodic status update task"""[m
         asyncio.create_task(self.__periodic_status_update())[m
[36m@@ -774,65 +764,48 @@[m [mclass BlockchainHandler:[m
                     self.report_status_to_oracle()[m
                     self.__last_status_update = datetime.now()[m
             except Exception as e:[m
[31m-                logging.error(f"Error in periodic status update: {e}")[m
[32m+[m[32m                logging.exception(f"Error in periodic status update: {e}")[m
             await asyncio.sleep(5)  # Check every 5 seconds[m
 [m
     def get_selected_clients(self, num_clients=None, criteria="random"):[m
         """Get selected clients for current round"""[m
         try:[m
[31m-            params = {[m
[31m-                "num_clients": num_clients,[m
[31m-                "criteria": criteria[m
[31m-            }[m
[32m+[m[32m            params = {"num_clients": num_clients, "criteria": criteria}[m
             response = requests.get([m
[31m-                url=f"{self.__oracle_url}/select_clients",[m
[31m-                params=params,[m
[31m-                headers=self.__rest_header,[m
[31m-                timeout=20[m
[32m+[m[32m                url=f"{self.__oracle_url}/select_clients", params=params, headers=self.__rest_header, timeout=20[m
             )[m
             return response.json()[m
         except Exception as e:[m
[31m-            logging.error(f"Error getting selected clients: {e}")[m
[32m+[m[32m            logging.exception(f"Error getting selected clients: {e}")[m
             return [][m
[31m-        [m
[32m+[m
     def track_model_version(self):[m
         data = {[m
[31m-            'client_id': self.__home_ip,[m
[31m-            'local_version': self.round,  [m
[31m-            'global_version': self.__global_version,[m
[31m-            'timestamp': datetime.now().isoformat(),[m
[31m-            'performance': self.__latest_performance[m
[32m+[m[32m            "client_id": self.__home_ip,[m
[32m+[m[32m            "local_version": self.round,[m
[32m+[m[32m            "global_version": self.__global_version,[m
[32m+[m[32m            "timestamp": datetime.now().isoformat(),[m
[32m+[m[32m            "performance": self.__latest_performance,[m
         }[m
         try:[m
[31m-            response = requests.post([m
[31m-                url=f"{self.__oracle_url}/model/version",[m
[31m-                json=data,[m
[31m-                headers=self.__rest_header[m
[31m-            )[m
[32m+[m[32m            response = requests.post(url=f"{self.__oracle_url}/model/version", json=data, headers=self.__rest_header)[m
             response.raise_for_status()[m
             return response.json()[m
         except Exception as e:[m
[31m-            logging.error(f"Failed to track model version: {e}")[m
[32m+[m[32m            logging.exception(f"Failed to track model version: {e}")[m
             return None[m
 [m
     def check_performance_and_replace(self, current_performance):[m
         try:[m
             # Report performance to Oracle[m
[31m-            data = {[m
[31m-                'client_id': self.__home_ip,[m
[31m-                'performance': current_performance[m
[31m-            }[m
[31m-            response = requests.post([m
[31m-                f"{self.__oracle_url}/model/performance",[m
[31m-                json=data,[m
[31m-                headers=self.__rest_header[m
[31m-            )[m
[31m-            [m
[31m-            if response.json().get('replace_model', False):[m
[32m+[m[32m            data = {"client_id": self.__home_ip, "performance": current_performance}[m
[32m+[m[32m            response = requests.post(f"{self.__oracle_url}/model/performance", json=data, headers=self.__rest_header)[m
[32m+[m
[32m+[m[32m            if response.json().get("replace_model", False):[m
                 self.handle_model_replacement()[m
[31m-                [m
[32m+[m
         except Exception as e:[m
[31m-            logging.error(f"Performance check failed: {e}")[m
[32m+[m[32m            logging.exception(f"Performance check failed: {e}")[m
 [m
     def handle_model_replacement(self):[m
         logging.info("Starting model replacement")[m
[36m@@ -842,85 +815,76 @@[m [mclass BlockchainHandler:[m
     def sync_model_versions(self):[m
         """Sync local and global model versions"""[m
         try:[m
[31m-            response = requests.get([m
[31m-                f"{self.__oracle_url}/model/versions/{self.__home_ip}",[m
[31m-                headers=self.__rest_header[m
[31m-            )[m
[32m+[m[32m            response = requests.get(f"{self.__oracle_url}/model/versions/{self.__home_ip}", headers=self.__rest_header)[m
             versions = response.json()[m
[31m-            if versions['current_global'] > self.__global_version:[m
[32m+[m[32m            if versions["current_global"] > self.__global_version:[m
                 logging.info(f"New global version available: {versions['current_global']}")[m
                 return self.handle_model_replacement()[m
             return False[m
         except Exception as e:[m
[31m-            logging.error(f"Version sync failed: {e}")[m
[32m+[m[32m            logging.exception(f"Version sync failed: {e}")[m
             return False[m
 [m
     def get_model_state(self, version):[m
         """Get model state from oracle"""[m
         try:[m
[31m-            response = requests.get([m
[31m-                f"{self.__oracle_url}/model/state/{version}",[m
[31m-                headers=self.__rest_header[m
[31m-            )[m
[31m-            return response.json().get('model_state')[m
[32m+[m[32m            response = requests.get(f"{self.__oracle_url}/model/state/{version}", headers=self.__rest_header)[m
[32m+[m[32m            return response.json().get("model_state")[m
         except Exception as e:[m
[31m-            logging.error(f"Failed to get model state: {e}")[m
[32m+[m[32m            logging.exception(f"Failed to get model state: {e}")[m
             return None[m
 [m
     def sync_model_state(self):[m
         """Sync model state with latest version"""[m
         latest = self.get_latest_model_version()[m
[31m-        if latest['version'] > self.__global_version:[m
[31m-            model_state = self.get_model_state(latest['version'])[m
[32m+[m[32m        if latest["version"] > self.__global_version:[m
[32m+[m[32m            model_state = self.get_model_state(latest["version"])[m
             if model_state:[m
                 self.__current_model = model_state[m
[31m-                self.__global_version = latest['version'][m
[32m+[m[32m                self.__global_version = latest["version"][m
                 return True[m
         return False[m
[31m-    [m
[32m+[m
     async def aggregate_with_version_sync(self):[m
         """Aggregation with version syncing"""[m
         if await self.sync_model_state():[m
             logging.info("Model state updated, restarting training")[m
             return True[m
[31m-            [m
[32m+[m
         performance = await self.calculate_performance()[m
         if performance < self.__performance_threshold:[m
             await self.check_performance_and_replace(performance)[m
[31m-            [m
[32m+[m
         await self.track_model_version()[m
         return False[m
[31m-    [m
[32m+[m
     def optimize_aggregation(self):[m
         """Adjust aggregation parameters based on benchmarks"""[m
         try:[m
             # Get optimization suggestions from Oracle[m
             response = requests.post([m
                 f"{self.__oracle_url}/optimization/benchmark",[m
[31m-                json={[m
[31m-                    'client_id': self.__home_ip,[m
[31m-                    'metrics': self.__optimization_metrics[m
[31m-                },[m
[31m-                headers=self.__rest_header[m
[32m+[m[32m                json={"client_id": self.__home_ip, "metrics": self.__optimization_metrics},[m
[32m+[m[32m                headers=self.__rest_header,[m
             )[m
[31m-        [m
[32m+[m
             suggestions = response.json()[m
[31m-        [m
[31m-            if suggestions.get('optimize_batch_size'):[m
[32m+[m
[32m+[m[32m            if suggestions.get("optimize_batch_size"):[m
                 self.__adjust_batch_size()[m
[31m-            [m
[31m-            if suggestions.get('adjust_learning_rate'):[m
[32m+[m
[32m+[m[32m            if suggestions.get("adjust_learning_rate"):[m
                 self.__adjust_learning_rate()[m
[31m-            [m
[32m+[m
             return suggestions[m
[31m-        [m
[32m+[m
         except Exception as e:[m
[31m-            logging.error(f"Optimization failed: {e}")[m
[32m+[m[32m            logging.exception(f"Optimization failed: {e}")[m
             return {}[m
 [m
     def __adjust_batch_size(self):[m
         """Adjust batch size based on communication overhead"""[m
[31m-        current_overhead = self.__optimization_metrics['communication_overhead'][m
[32m+[m[32m        current_overhead = self.__optimization_metrics["communication_overhead"][m
         if current_overhead > 1000:  # threshold[m
             self.__batch_size = max(32, self.__batch_size // 2)[m
         else:[m
[36m@@ -928,7 +892,7 @@[m [mclass BlockchainHandler:[m
 [m
     def __adjust_learning_rate(self):[m
         """Adjust learning rate based on convergence"""[m
[31m-        current_rate = self.__optimization_metrics['convergence_rate'][m
[32m+[m[32m        current_rate = self.__optimization_metrics["convergence_rate"][m
         if current_rate < 0.001:  # threshold[m
             self.__learning_rate *= 1.5[m
         else:[m
[36m@@ -937,52 +901,52 @@[m [mclass BlockchainHandler:[m
     async def optimized_aggregation(self):[m
         """Perform aggregation with optimization"""[m
         start_time = time.time()[m
[31m-    [m
[32m+[m
         try:[m
             # Regular aggregation[m
             result = await self.aggregate_with_version_sync()[m
[31m-        [m
[32m+[m
             # Update metrics[m
             self.__optimization_metrics.update({[m
[31m-                'aggregation_time': time.time() - start_time,[m
[31m-                'convergence_rate': self._calculate_convergence_rate(),[m
[31m-                'communication_overhead': self._calculate_communication_overhead()[m
[32m+[m[32m                "aggregation_time": time.time() - start_time,[m
[32m+[m[32m                "convergence_rate": self._calculate_convergence_rate(),[m
[32m+[m[32m                "communication_overhead": self._calculate_communication_overhead(),[m
             })[m
[31m-        [m
[32m+[m
             # Benchmark and optimize[m
             await self.benchmark_performance()[m
             optimization_result = self.optimize_aggregation()[m
[31m-        [m
[32m+[m
             logging.info(f"Optimization metrics: {self.__optimization_metrics}")[m
             logging.info(f"Optimization suggestions: {optimization_result}")[m
[31m-        [m
[32m+[m
             return result[m
[31m-        [m
[32m+[m
         except Exception as e:[m
[31m-            logging.error(f"Optimized aggregation failed: {e}")[m
[32m+[m[32m            logging.exception(f"Optimized aggregation failed: {e}")[m
             return False[m
 [m
     def _calculate_convergence_rate(self):[m
         """Calculate convergence rate from recent rounds"""[m
         if len(self.__benchmark_data) < 2:[m
             return 0[m
[31m-    [m
[32m+[m
         recent = self.__benchmark_data[-2:][m
[31m-        return abs(recent[1].get('performance', 0) - recent[0].get('performance', 0))[m
[32m+[m[32m        return abs(recent[1].get("performance", 0) - recent[0].get("performance", 0))[m
 [m
     def _calculate_communication_overhead(self):[m
         """Calculate communication overhead"""[m
         return sum(len(str(d)) for d in self.__benchmark_data[-1:])  # Simple estimation[m
[31m-    [m
[32m+[m
     async def set_aggregation_mode(self, mode, central_node=None):[m
         """Switch between centralized and decentralized modes"""[m
         if mode not in ["centralized", "decentralized"]:[m
             logging.error(f"Invalid aggregation mode: {mode}")[m
             return False[m
[31m-            [m
[32m+[m
         self.__aggregation_mode = mode[m
         self.__central_node = central_node[m
[31m-        [m
[32m+[m
         # Update Oracle about mode change[m
         await self.report_mode_change(mode)[m
         return True[m
[36m@@ -993,7 +957,7 @@[m [mclass BlockchainHandler:[m
             return await self._centralized_aggregation()[m
         else:[m
             return await self._decentralized_aggregation()[m
[31m-        [m
[32m+[m
     async def _centralized_aggregation(self):[m
         """Centralized aggregation mode"""[m
         try:[m
[36m@@ -1010,7 +974,7 @@[m [mclass BlockchainHandler:[m
                     logging.info(f"Sending model to central node: {self.__central_node}")[m
                     return await self._send_model_to_central()[m
         except Exception as e:[m
[31m-            logging.error(f"Centralized aggregation failed: {e}")[m
[32m+[m[32m            logging.exception(f"Centralized aggregation failed: {e}")[m
             return False[m
 [m
     async def _decentralized_aggregation(self):[m
[36m@@ -1021,13 +985,12 @@[m [mclass BlockchainHandler:[m
             if not active_nodes:[m
                 logging.warning("No active nodes for decentralized aggregation")[m
                 return False[m
[31m-            [m
[32m+[m
             # Exchange models with neighbors[m
             neighbor_models = await self._exchange_models(active_nodes)[m
[31m-        [m
[31m-        # Local aggregation[m
[32m+[m
[32m+[m[32m            # Local aggregation[m
             return await self._aggregate_models(neighbor_models)[m
         except Exception as e:[m
[31m-            logging.error(f"Decentralized aggregation failed: {e}")[m
[32m+[m[32m            logging.exception(f"Decentralized aggregation failed: {e}")[m
             return False[m
[31m-[m
[1mdiff --git a/nebula/tests/aggregation.json b/nebula/tests/aggregation.json[m
[1mindex 2c8c809..5aabd32 100644[m
[1m--- a/nebula/tests/aggregation.json[m
[1m+++ b/nebula/tests/aggregation.json[m
[36m@@ -766,7 +766,7 @@[m
         "id": 4,[m
         "ip": "192.168.50.6",[m
         "port": "45000",[m
[31m-        "role": "aggregator", [m
[32m+[m[32m        "role": "aggregator",[m
         "malicious": false,[m
         "proxy": false,[m
         "start": false[m
[36m@@ -790,7 +790,7 @@[m
       },[m
       {[m
         "id": 1,[m
[31m-        "ip": "192.168.50.3", [m
[32m+[m[32m        "ip": "192.168.50.3",[m
         "port": "45000",[m
         "role": "aggregator",[m
         "malicious": false,[m
[36m@@ -806,7 +806,7 @@[m
       {[m
         "id": 2,[m
         "ip": "192.168.50.4",[m
[31m-        "port": "45000", [m
[32m+[m[32m        "port": "45000",[m
         "role": "aggregator",[m
         "malicious": false,[m
         "proxy": false,[m
[36m@@ -822,7 +822,7 @@[m
         "id": 3,[m
         "ip": "192.168.50.5",[m
         "port": "45000",[m
[31m-        "role": "aggregator", [m
[32m+[m[32m        "role": "aggregator",[m
         "malicious": false,[m
         "proxy": false,[m
         "start": false,[m
[36m@@ -839,7 +839,7 @@[m
         "port": "45000",[m
         "role": "aggregator",[m
         "malicious": false,[m
[31m-        "proxy": false, [m
[32m+[m[32m        "proxy": false,[m
         "start": false,[m
         "neighbors": [0, 1, 2, 3],[m
         "links": [],[m
