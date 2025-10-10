import json
import csv
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
            records = [record.data() for record in result]
            if return_type == "json":
                return json.dumps(records, indent=2)
            elif return_type == "csv":
                if records:
                    keys = records[0].keys()
                    output = csv.StringIO()
                    writer = csv.DictWriter(output, fieldnames=keys)
                    writer.writeheader()
                    writer.writerows(records)
                    return output.getvalue()
                else:
                    return ""
            else:
                return records


