#!/usr/bin/env python3
"""
Tests for the update_kg.py utility.
"""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from update_kg import split_cypher_statements, load_cypher_query, execute_update


class TestCypherStatementSplitting(unittest.TestCase):
    """Test the Cypher statement splitting functionality."""

    def test_single_statement(self):
        """Test splitting a single statement."""
        query = "CREATE (n:Node {name: 'test'})"
        statements = split_cypher_statements(query)
        self.assertEqual(len(statements), 1)
        self.assertEqual(statements[0], query)

    def test_multiple_statements_with_semicolons(self):
        """Test splitting multiple statements separated by semicolons."""
        query = """
        CREATE (n:Node {name: 'test1'});
        CREATE (m:Node {name: 'test2'});
        MATCH (n), (m) CREATE (n)-[:RELATES_TO]->(m)
        """
        statements = split_cypher_statements(query)
        self.assertEqual(len(statements), 3)
        self.assertIn("CREATE (n:Node {name: 'test1'})", statements[0])
        self.assertIn("CREATE (m:Node {name: 'test2'})", statements[1])
        self.assertIn("MATCH (n), (m) CREATE (n)-[:RELATES_TO]->(m)", statements[2])

    def test_semicolon_in_string_literal(self):
        """Test that semicolons inside string literals are preserved."""
        query = """
        CREATE (n:Node {description: 'This; has; semicolons'});
        CREATE (m:Node {name: 'test'})
        """
        statements = split_cypher_statements(query)
        self.assertEqual(len(statements), 2)
        self.assertIn("This; has; semicolons", statements[0])
        self.assertIn("CREATE (m:Node", statements[1])

    def test_double_quoted_strings(self):
        """Test handling of double-quoted strings."""
        query = """
        CREATE (n:Node {description: "This; has; semicolons"});
        CREATE (m:Node {name: "test"})
        """
        statements = split_cypher_statements(query)
        self.assertEqual(len(statements), 2)
        self.assertIn('description: "This; has; semicolons"', statements[0])

    def test_comments_only_statements_filtered(self):
        """Test that comment-only statements are filtered out."""
        query = """
        // This is just a comment;
        CREATE (n:Node {name: 'test'});
        // Another comment
        """
        statements = split_cypher_statements(query)
        self.assertEqual(len(statements), 1)
        self.assertIn("CREATE (n:Node", statements[0])

    def test_mixed_comments_and_code(self):
        """Test statements with both comments and code."""
        query = """
        // Create a test node
        CREATE (n:Node {name: 'test'});
        // Create another node
        CREATE (m:Node {name: 'test2'})
        """
        statements = split_cypher_statements(query)
        self.assertEqual(len(statements), 2)
        self.assertIn("CREATE (n:Node", statements[0])
        self.assertIn("CREATE (m:Node", statements[1])

    def test_empty_query(self):
        """Test handling of empty queries."""
        statements = split_cypher_statements("")
        self.assertEqual(len(statements), 0)

    def test_whitespace_only_query(self):
        """Test handling of whitespace-only queries."""
        statements = split_cypher_statements("   \n\t  ")
        self.assertEqual(len(statements), 0)

    def test_trailing_semicolon(self):
        """Test handling of trailing semicolons."""
        query = "CREATE (n:Node {name: 'test'});"
        statements = split_cypher_statements(query)
        self.assertEqual(len(statements), 1)
        self.assertEqual(statements[0], "CREATE (n:Node {name: 'test'})")


class TestFileLoading(unittest.TestCase):
    """Test file loading functionality."""

    def test_load_cypher_query(self):
        """Test loading a Cypher query from a file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cypher', delete=False) as f:
            test_query = "CREATE (n:Node {name: 'test'})"
            f.write(test_query)
            f.flush()

            loaded_query = load_cypher_query(f.name)
            self.assertEqual(loaded_query, test_query)

            # Clean up
            Path(f.name).unlink()


class TestExecuteUpdate(unittest.TestCase):
    """Test the execute_update function with mocked Neo4j."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_file = tempfile.NamedTemporaryFile(mode='w', suffix='.cypher', delete=False)
        self.test_file_path = Path(self.test_file.name)

    def tearDown(self):
        """Clean up test fixtures."""
        if self.test_file_path.exists():
            self.test_file_path.unlink()

    def test_dry_run_single_statement(self):
        """Test dry run with a single statement."""
        query = "CREATE (n:Node {name: 'test'})"
        self.test_file.write(query)
        self.test_file.close()

        # Capture output
        with patch('builtins.print') as mock_print:
            result = execute_update(self.test_file_path, "localhost", "7687", "neo4j", "neo", dry_run=True)

            self.assertTrue(result)
            # Check that dry run output was printed
            print_calls = [call.args[0] for call in mock_print.call_args_list]
            self.assertTrue(any("DRY RUN" in call for call in print_calls))
            self.assertTrue(any("CREATE (n:Node" in call for call in print_calls))

    def test_dry_run_multiple_statements(self):
        """Test dry run with multiple statements."""
        query = """
        CREATE (n:Node {name: 'test1'});
        CREATE (m:Node {name: 'test2'});
        MATCH (n), (m) CREATE (n)-[:RELATES_TO]->(m)
        """
        self.test_file.write(query)
        self.test_file.close()

        with patch('builtins.print') as mock_print:
            result = execute_update(self.test_file_path, "localhost", "7687", "neo4j", "neo", dry_run=True)

            self.assertTrue(result)
            print_calls = [call.args[0] for call in mock_print.call_args_list]
            self.assertTrue(any("3 statement(s)" in call for call in print_calls))

    @patch('update_kg.Neo4jBoltQueryWrapper')
    def test_execute_single_statement_success(self, mock_wrapper_class):
        """Test successful execution of a single statement."""
        # Setup mock
        mock_wrapper = Mock()
        mock_wrapper.run_query.return_value = []
        mock_wrapper_class.return_value = mock_wrapper

        query = "CREATE (n:Node {name: 'test'})"
        self.test_file.write(query)
        self.test_file.close()

        result = execute_update(self.test_file_path, "localhost", "7687", "neo4j", "neo", dry_run=False)

        self.assertTrue(result)
        mock_wrapper.run_query.assert_called_once_with(query, return_type="records")

    @patch('update_kg.Neo4jBoltQueryWrapper')
    def test_execute_multiple_statements_success(self, mock_wrapper_class):
        """Test successful execution of multiple statements."""
        # Setup mock
        mock_wrapper = Mock()
        mock_wrapper.run_query.return_value = []
        mock_wrapper_class.return_value = mock_wrapper

        query = """
        CREATE (n:Node {name: 'test1'});
        CREATE (m:Node {name: 'test2'})
        """
        self.test_file.write(query)
        self.test_file.close()

        result = execute_update(self.test_file_path, "localhost", "7687", "neo4j", "neo", dry_run=False)

        self.assertTrue(result)
        self.assertEqual(mock_wrapper.run_query.call_count, 2)

    @patch('update_kg.Neo4jBoltQueryWrapper')
    def test_execute_statement_with_error_fail_fast(self, mock_wrapper_class):
        """Test execution with error in fail-fast mode."""
        # Setup mock to fail on second statement
        mock_wrapper = Mock()
        mock_wrapper.run_query.side_effect = [[], Exception("Test error")]
        mock_wrapper_class.return_value = mock_wrapper

        query = """
        CREATE (n:Node {name: 'test1'});
        INVALID CYPHER STATEMENT
        """
        self.test_file.write(query)
        self.test_file.close()

        result = execute_update(self.test_file_path, "localhost", "7687", "neo4j", "neo",
                              dry_run=False, fail_fast=True)

        self.assertFalse(result)
        self.assertEqual(mock_wrapper.run_query.call_count, 2)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)