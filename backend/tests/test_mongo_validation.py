import pytest

from app.db.mongo import MongoService


class TestMongoServiceInit:
    def test_raises_on_empty_uri(self):
        with pytest.raises(ValueError, match="MONGODB_URI is required"):
            MongoService("", "test_db")


class TestSetNodeProgress:
    @pytest.fixture
    def mongo(self):
        """Create MongoService with a dummy URI (won't actually connect)."""
        return MongoService("mongodb://localhost:27017", "test_db")

    async def test_rejects_dot_in_node_name(self, mongo):
        with pytest.raises(ValueError, match="Invalid node name"):
            await mongo.set_node_progress(
                "run-1", node="some.node", payload={"status": "start"}
            )

    async def test_rejects_dollar_prefix(self, mongo):
        with pytest.raises(ValueError, match="Invalid node name"):
            await mongo.set_node_progress(
                "run-1", node="$inject", payload={"status": "start"}
            )

    async def test_valid_node_name_does_not_raise(self, mongo):
        """Valid node names should not raise (will fail at DB level but not validation)."""
        # Mock the update_one to avoid actual DB call
        from unittest.mock import AsyncMock
        mongo.runs = AsyncMock()
        mongo.runs.update_one = AsyncMock()

        # Should not raise ValueError
        await mongo.set_node_progress(
            "run-1", node="ParseRequest", payload={"status": "start"}
        )
        mongo.runs.update_one.assert_called_once()
