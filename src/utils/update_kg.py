#!/usr/bin/env python3
"""
Knowledge graph update utility that executes Cypher update statements.
Used by Makefile to apply modifications to the knowledge graph.
"""

import argparse
import sys
import re
import logging
from datetime import datetime
from pathlib import Path
from neo4j_bolt_wrapper import Neo4jBoltQueryWrapper


def load_cypher_query(query_file):
    """Load Cypher query from file."""
    with open(query_file, 'r') as f:
        return f.read().strip()


def split_cypher_statements(query_text):
    """
    Split Cypher query text into individual statements.
    Handles semicolon delimiters while preserving statements with embedded semicolons in strings.
    """
    if not query_text.strip():
        return []

    statements = []
    current_statement = ""
    in_string = False
    string_char = None
    i = 0

    while i < len(query_text):
        char = query_text[i]

        # Handle string literals (single or double quotes)
        if char in ('"', "'") and (i == 0 or query_text[i-1] != '\\'):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None

        # Handle semicolon delimiters
        elif char == ';' and not in_string:
            if current_statement.strip():
                statements.append(current_statement.strip())
            current_statement = ""
            i += 1
            continue

        current_statement += char
        i += 1

    # Add the last statement if it exists
    if current_statement.strip():
        statements.append(current_statement.strip())

    # Filter out comments-only statements
    filtered_statements = []
    for stmt in statements:
        # Remove single-line comments and check if anything remains
        lines = stmt.split('\n')
        non_comment_lines = [line.strip() for line in lines
                           if line.strip() and not line.strip().startswith('//')]
        if non_comment_lines:
            filtered_statements.append(stmt)

    return filtered_statements


def format_execution_stats(stats):
    """Format execution statistics for display."""
    if not stats:
        return "No statistics available"

    significant_stats = []
    for key, value in stats.items():
        if key in ['result_available_after', 'result_consumed_after']:
            continue  # Skip timing stats for now
        if value > 0:
            significant_stats.append(f"{key}: {value}")

    if significant_stats:
        return ", ".join(significant_stats)
    else:
        return "No changes made"


def setup_logging(log_file=None):
    """Setup logging configuration."""
    log_format = '%(asctime)s - %(levelname)s - %(message)s'

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[]
    )

    logger = logging.getLogger('kg_update')
    logger.handlers.clear()  # Clear any existing handlers

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(log_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def execute_update(query_file, host, port, user, password, dry_run=False, fail_fast=True, logger=None):
    """Execute Cypher update statements against the knowledge graph."""
    if logger is None:
        logger = logging.getLogger('kg_update')

    try:
        # Load and split query
        query_text = load_cypher_query(query_file)
        if not query_text:
            raise ValueError(f"Empty query file: {query_file}")

        statements = split_cypher_statements(query_text)
        if not statements:
            logger.info(f"No executable statements found in {query_file}")
            return True

        if dry_run:
            logger.info(f"DRY RUN - Would execute {len(statements)} statement(s) from {query_file}:")
            for i, stmt in enumerate(statements, 1):
                print(f"Statement {i}:")
                print(f"{stmt}\n")
            return True

        # Connect to Neo4j
        endpoint = f"bolt://{host}:{port}"
        wrapper = Neo4jBoltQueryWrapper(endpoint, user, password)

        logger.info(f"Executing {len(statements)} statement(s) from {query_file}")

        # Execute statements and track results
        success_count = 0
        total_stats = {
            'nodes_created': 0, 'nodes_deleted': 0,
            'relationships_created': 0, 'relationships_deleted': 0,
            'properties_set': 0, 'labels_added': 0, 'labels_removed': 0,
            'indexes_added': 0, 'indexes_removed': 0,
            'constraints_added': 0, 'constraints_removed': 0
        }

        for i, statement in enumerate(statements, 1):
            try:
                logger.info(f"  Statement {i}/{len(statements)}...")

                # Get both records and stats in one call
                result = wrapper.run_query(statement, return_type="records_and_summary")
                records = result['records']
                stats = result['stats']

                success_count += 1

                # Accumulate statistics
                for key in total_stats:
                    if key in stats:
                        total_stats[key] += stats[key]

                # Show result summary
                stats_summary = format_execution_stats(stats)
                logger.info(f"    → {stats_summary}")

                if records and len(records) > 0:
                    logger.info(f"    → Returned {len(records)} record(s)")

            except Exception as e:
                logger.error(f"Error in statement {i}: {e}")
                if fail_fast:
                    logger.error(f"Stopping execution due to error (executed {success_count}/{len(statements)} statements)")
                    return False
                else:
                    logger.warning(f"Continuing with remaining statements...")

        # Log final summary
        final_summary = format_execution_stats(total_stats)
        logger.info(f"File execution complete: {final_summary}")
        logger.info(f"Successfully executed {success_count}/{len(statements)} statements from {query_file}")

        return success_count == len(statements)

    except Exception as e:
        logger.error(f"Error processing file {query_file}: {e}")
        return False


def execute_updates_directory(updates_dir, host, port, user, password, dry_run=False, fail_fast=True, log_file=None):
    """Execute all Cypher update files in a directory in alphabetical order."""
    # Setup logging
    logger = setup_logging(log_file)

    updates_path = Path(updates_dir)
    if not updates_path.exists():
        logger.warning(f"Updates directory does not exist: {updates_dir}")
        return True

    # Get all .cypher files and sort them
    cypher_files = sorted(updates_path.glob("*.cypher"))

    if not cypher_files:
        logger.info(f"No .cypher files found in {updates_dir}")
        return True

    # Log execution start
    timestamp = datetime.now().isoformat()
    logger.info(f"=== Knowledge Graph Update Session Started ===")
    logger.info(f"Timestamp: {timestamp}")
    logger.info(f"Updates directory: {updates_dir}")
    logger.info(f"Found {len(cypher_files)} update files")
    logger.info(f"Neo4j endpoint: bolt://{host}:{port}")
    logger.info(f"Fail fast mode: {fail_fast}")

    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    success_count = 0
    overall_stats = {
        'nodes_created': 0, 'nodes_deleted': 0,
        'relationships_created': 0, 'relationships_deleted': 0,
        'properties_set': 0, 'labels_added': 0, 'labels_removed': 0,
        'indexes_added': 0, 'indexes_removed': 0,
        'constraints_added': 0, 'constraints_removed': 0
    }

    for cypher_file in cypher_files:
        logger.info(f"\n--- Processing: {cypher_file.name} ---")
        if execute_update(cypher_file, host, port, user, password, dry_run, fail_fast, logger):
            success_count += 1
        else:
            logger.error(f"Failed to execute: {cypher_file}")
            if fail_fast:
                logger.error(f"Stopping due to error (executed {success_count}/{len(cypher_files)} files)")
                break

    # Log final summary
    logger.info(f"\n=== Update Session Complete ===")
    logger.info(f"Files processed: {success_count}/{len(cypher_files)}")

    if not dry_run and success_count > 0:
        final_summary = format_execution_stats(overall_stats)
        logger.info(f"Overall changes: {final_summary}")

    logger.info(f"Session ended: {datetime.now().isoformat()}")

    return success_count == len(cypher_files)


def main():
    parser = argparse.ArgumentParser(description="Execute Cypher update statements against knowledge graph")
    parser.add_argument("--updates-dir", required=True, help="Directory containing Cypher update files")
    parser.add_argument("--host", default="localhost", help="Neo4j host")
    parser.add_argument("--port", default="7687", help="Neo4j port")
    parser.add_argument("--user", default="neo4j", help="Neo4j username")
    parser.add_argument("--password", default="neo", help="Neo4j password")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be executed without running")
    parser.add_argument("--continue-on-error", action="store_true",
                       help="Continue executing remaining statements/files after errors")
    parser.add_argument("--log-file", help="Log file path for execution details")

    args = parser.parse_args()

    success = execute_updates_directory(
        args.updates_dir, args.host, args.port, args.user, args.password,
        args.dry_run, fail_fast=not args.continue_on_error, log_file=args.log_file
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()