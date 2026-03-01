"""Neo4j client for knowledge graph operations."""

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable
from datetime import datetime, timezone
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncManagedTransaction
from neo4j.exceptions import ClientError, ServiceUnavailable

from src.config.settings import settings

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Async Neo4j client for knowledge graph operations."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ) -> None:
        """Initialize Neo4j client.

        Args:
            uri: Neo4j connection URI
            user: Database user
            password: Database password
            database: Database name
        """
        self.uri = uri or settings.neo4j_uri
        self.user = user or settings.neo4j_user
        self.password = password or settings.neo4j_password
        self.database = database or settings.neo4j_database

        self._driver: Any = None
        self._is_connected = False

    async def connect(self) -> None:
        """Connect to Neo4j database."""
        if self._is_connected:
            logger.warning("Already connected to Neo4j")
            return

        try:
            self._driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60,
            )

            # Verify connectivity
            await self._driver.verify_connectivity()

            self._is_connected = True
            logger.info(f"Connected to Neo4j at {self.uri}")

        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self._is_connected = False
            raise

    async def disconnect(self) -> None:
        """Disconnect from Neo4j database."""
        if not self._is_connected:
            return

        try:
            if self._driver:
                await self._driver.close()
                self._driver = None

            self._is_connected = False
            logger.info("Disconnected from Neo4j")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")

    async def execute_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records
        """
        if not self._is_connected:
            await self.connect()

        try:
            async with self._driver.session(database=self.database) as session:
                result = await session.run(query, parameters or {})
                records = await result.data()
                return records

        except ClientError as e:
            logger.error(f"Query execution failed: {e}")
            raise

        except ServiceUnavailable as e:
            logger.error(f"Neo4j service unavailable: {e}")
            raise

    async def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a write query.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            Result summary
        """
        if not self._is_connected:
            await self.connect()

        try:
            async with self._driver.session(database=self.database) as session:
                result = await session.run(query, parameters or {})
                summary = await result.consume()
                return summary

        except Exception as e:
            logger.error(f"Write query failed: {e}")
            raise

    async def execute_transaction(
        self,
        transaction_fn: Callable[[AsyncManagedTransaction], Any],
    ) -> Any:
        """Execute a transaction.

        Args:
            transaction_fn: Transaction function

        Returns:
            Transaction result
        """
        if not self._is_connected:
            await self.connect()

        try:
            async with self._driver.session(database=self.database) as session:
                result = await session.execute_write(transaction_fn)
                return result

        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            raise

    @property
    def is_connected(self) -> bool:
        """Check if connected to Neo4j."""
        return self._is_connected

    async def create_node(
        self,
        label: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a node.

        Args:
            label: Node label
            properties: Node properties

        Returns:
            Created node data
        """
        query = f"""
        CREATE (n:{label} $properties)
        RETURN n
        """

        results = await self.execute_query(query, {"properties": properties})

        if results:
            return dict(results[0]["n"])

        return {}

    async def get_node(
        self,
        label: str,
        property_name: str,
        property_value: Any,
    ) -> dict[str, Any] | None:
        """Get a node by property.

        Args:
            label: Node label
            property_name: Property name to match
            property_value: Property value

        Returns:
            Node data or None
        """
        query = f"""
        MATCH (n:{label} {{{property_name}: $value}})
        RETURN n
        LIMIT 1
        """

        results = await self.execute_query(query, {"value": property_value})

        if results:
            return dict(results[0]["n"])

        return None

    async def update_node(
        self,
        label: str,
        property_name: str,
        property_value: Any,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update a node.

        Args:
            label: Node label
            property_name: Property name to match
            property_value: Property value
            updates: Properties to update

        Returns:
            Updated node data or None
        """
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()

        query = f"""
        MATCH (n:{label} {{{property_name}: $value}})
        SET n += $updates
        RETURN n
        """

        results = await self.execute_query(
            query,
            {"value": property_value, "updates": updates},
        )

        if results:
            return dict(results[0]["n"])

        return None

    async def delete_node(
        self,
        label: str,
        property_name: str,
        property_value: Any,
    ) -> bool:
        """Delete a node.

        Args:
            label: Node label
            property_name: Property name to match
            property_value: Property value

        Returns:
            True if deleted
        """
        query = f"""
        MATCH (n:{label} {{{property_name}: $value}})
        DETACH DELETE n
        """

        try:
            await self.execute_write(query, {"value": property_value})
            return True

        except Exception:
            return False

    async def create_relationship(
        self,
        from_label: str,
        from_property: str,
        from_value: Any,
        to_label: str,
        to_property: str,
        to_value: Any,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Create a relationship between nodes.

        Args:
            from_label: Source node label
            from_property: Source node property
            from_value: Source node value
            to_label: Target node label
            to_property: Target node property
            to_value: Target node value
            relationship_type: Type of relationship
            properties: Optional relationship properties

        Returns:
            Relationship data or None
        """
        query = f"""
        MATCH (a:{from_label} {{{from_property}: $from_value}})
        MATCH (b:{to_label} {{{to_property}: $to_value}})
        CREATE (a)-[r:{relationship_type} $properties]->(b)
        RETURN r
        """

        results = await self.execute_query(
            query,
            {
                "from_value": from_value,
                "to_value": to_value,
                "properties": properties or {},
            },
        )

        if results:
            return dict(results[0]["r"])

        return None

    async def get_relationships(
        self,
        label: str,
        property_name: str,
        property_value: Any,
        direction: str = "outgoing",
    ) -> list[dict[str, Any]]:
        """Get relationships for a node.

        Args:
            label: Node label
            property_name: Property name to match
            property_value: Property value
            direction: "outgoing", "incoming", or "both"

        Returns:
            List of relationships
        """
        if direction == "outgoing":
            arrow = "-[r]->"
        elif direction == "incoming":
            arrow = "<-[r]-"
        else:
            arrow = "-[r]-"

        query = f"""
        MATCH (n:{label} {{{property_name}: $value}}){arrow}(m)
        RETURN r, type(r) as relationship_type, labels(m) as target_labels
        """

        results = await self.execute_query(query, {"value": property_value})

        return [
            {
                "relationship": dict(r["r"]),
                "type": r["relationship_type"],
                "target_labels": r["target_labels"],
            }
            for r in results
        ]

    async def find_path(
        self,
        from_label: str,
        from_property: str,
        from_value: Any,
        to_label: str,
        to_property: str,
        to_value: Any,
        max_depth: int = 5,
    ) -> list[dict[str, Any]]:
        """Find shortest path between nodes.

        Args:
            from_label: Source node label
            from_property: Source node property
            from_value: Source node value
            to_label: Target node label
            to_property: Target node property
            to_value: Target node value
            max_depth: Maximum path depth

        Returns:
            List of nodes in path
        """
        query = f"""
        MATCH (a:{from_label} {{{from_property}: $from_value}})
        MATCH (b:{to_label} {{{to_property}: $to_value}})
        MATCH path = shortestPath((a)-[*1..{max_depth}]-(b))
        RETURN [node in nodes(path) | properties(node)] as nodes
        """

        results = await self.execute_query(
            query,
            {"from_value": from_value, "to_value": to_value},
        )

        if results:
            return results[0]["nodes"]

        return []

    async def query_by_pattern(
        self,
        pattern: str,
        where_clause: str | None = None,
        return_clause: str = "n",
    ) -> list[dict[str, Any]]:
        """Query nodes by pattern matching.

        Args:
            pattern: Cypher pattern (e.g., "(n:User)-[:KNOWS]->(m:User)")
            where_clause: Optional WHERE clause
            return_clause: RETURN clause

        Returns:
            List of results
        """
        query = f"MATCH {pattern}"

        if where_clause:
            query += f" WHERE {where_clause}"

        query += f" RETURN {return_clause}"

        return await self.execute_query(query)

    async def batch_create_nodes(
        self,
        label: str,
        nodes: list[dict[str, Any]],
        batch_size: int = 1000,
    ) -> int:
        """Create nodes in batches.

        Args:
            label: Node label
            nodes: List of node properties
            batch_size: Batch size

        Returns:
            Number of nodes created
        """
        query = f"""
        UNWIND $batch as row
        CREATE (n:{label})
        SET n = row
        """

        total_created = 0

        for i in range(0, len(nodes), batch_size):
            batch = nodes[i : i + batch_size]
            await self.execute_write(query, {"batch": batch})
            total_created += len(batch)

        return total_created

    async def get_graph_stats(self) -> dict[str, Any]:
        """Get database statistics.

        Returns:
            Graph statistics
        """
        stats_query = """
        MATCH (n)
        WITH count(n) as node_count
        MATCH ()-[r]->()
        RETURN node_count, count(r) as relationship_count
        """

        results = await self.execute_query(stats_query)

        if results:
            return {
                "node_count": results[0]["node_count"],
                "relationship_count": results[0]["relationship_count"],
            }

        return {"node_count": 0, "relationship_count": 0}

    async def clear_database(self) -> bool:
        """Clear all nodes and relationships.

        Returns:
            True if successful
        """
        query = "MATCH (n) DETACH DELETE n"

        try:
            await self.execute_write(query)
            return True

        except Exception as e:
            logger.error(f"Failed to clear database: {e}")
            return False

    def __repr__(self) -> str:
        """String representation."""
        return f"Neo4jClient(uri={self.uri}, database={self.database})"


class Neo4jPool:
    """Pool of Neo4j clients for concurrent operations."""

    def __init__(
        self,
        max_clients: int = 5,
    ) -> None:
        """Initialize pool.

        Args:
            max_clients: Maximum number of clients
        """
        self.max_clients = max_clients
        self._clients: list[Neo4jClient] = []
        self._semaphore = asyncio.Semaphore(max_clients)

    async def acquire(self) -> Neo4jClient:
        """Acquire a client from the pool.

        Returns:
            Neo4j client
        """
        await self._semaphore.acquire()

        if self._clients:
            return self._clients.pop()

        client = Neo4jClient()
        await client.connect()
        return client

    async def release(self, client: Neo4jClient) -> None:
        """Release a client back to the pool.

        Args:
            client: Client to release
        """
        if len(self._clients) < self.max_clients:
            self._clients.append(client)
        else:
            await client.disconnect()

        self._semaphore.release()

    async def cleanup_all(self) -> None:
        """Clean up all clients in the pool."""
        for client in self._clients:
            await client.disconnect()

        self._clients.clear()


# Global client instance
_global_client: Neo4jClient | None = None


async def get_neo4j_client() -> Neo4jClient:
    """Get global Neo4j client.

    Returns:
        Neo4j client instance
    """
    global _global_client

    if _global_client is None:
        _global_client = Neo4jClient()
        await _global_client.connect()

    return _global_client
