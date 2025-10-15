import json
import csv
import logging
from io import StringIO
from neo4j import GraphDatabase, basic_auth

class Neo4jBoltQueryWrapper:
    def __init__(self, endpoint, user=None, password=None, test_connection=True):
        self.endpoint = endpoint
        self.user = user
        self.password = password
        self.driver = None
        self.connected = False
        if test_connection:
            self.connect()

    def connect(self):
        try:
            if self.user and self.password:
                self.driver = GraphDatabase.driver(self.endpoint, auth=basic_auth(self.user, self.password))
            else:
                self.driver = GraphDatabase.driver(self.endpoint)
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            self.connected = True
        except Exception as e:
            self.connected = False
            raise ConnectionError(f"Failed to connect to Neo4j: {e}")

    def test_connection(self):
        if not self.driver:
            self.connect()
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 1")
                return result.single()[0] == 1
        except Exception as e:
            return False

    def run_query(self, query, parameters=None, return_type="json"):
        if not self.driver:
            self.connect()
        with self.driver.session() as session:
            result = session.run(query, parameters or {})

            # Collect records first
            records = [record.data() for record in result]

            # Then consume summary
            summary = result.consume()

            # Get execution statistics
            stats = {
                'nodes_created': summary.counters.nodes_created,
                'nodes_deleted': summary.counters.nodes_deleted,
                'relationships_created': summary.counters.relationships_created,
                'relationships_deleted': summary.counters.relationships_deleted,
                'properties_set': summary.counters.properties_set,
                'labels_added': summary.counters.labels_added,
                'labels_removed': summary.counters.labels_removed,
                'indexes_added': summary.counters.indexes_added,
                'indexes_removed': summary.counters.indexes_removed,
                'constraints_added': summary.counters.constraints_added,
                'constraints_removed': summary.counters.constraints_removed,
                'result_available_after': summary.result_available_after,
                'result_consumed_after': summary.result_consumed_after
            }

            if return_type == "json":
                return json.dumps(records, indent=2)
            elif return_type == "csv":
                if records:
                    keys = records[0].keys()
                    output = StringIO()
                    writer = csv.DictWriter(output, fieldnames=keys)
                    writer.writeheader()
                    writer.writerows(records)
                    return output.getvalue()
                else:
                    return ""
            elif return_type == "summary":
                return stats
            elif return_type == "records_and_summary":
                return {'records': records, 'stats': stats}
            else:
                return records


