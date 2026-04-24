"""Built-in MCP prompt templates."""

from mcp.server.fastmcp import FastMCP


def register_prompts(server: FastMCP, settings) -> None:
    """Register built-in MCP prompt templates."""

    @server.prompt(
        name="ask-kb",
        description="Ask a question and get an answer grounded in the knowledge base.",
    )
    def ask_kb(question: str) -> str:
        """Ask a question against the knowledge base.

        Args:
            question: The question to ask.
        """
        return (
            f"Use the `chat` tool to answer this question using the knowledge base:\n\n{question}"
        )

    @server.prompt(
        name="summarize-topic",
        description="Search the knowledge base and summarize what it says about a topic.",
    )
    def summarize_topic(topic: str) -> str:
        """Summarize knowledge-base content about a topic.

        Args:
            topic: The topic to summarize.
        """
        return (
            f"Use the `search_summarize` tool to find and summarize everything "
            f"the knowledge base contains about: {topic}"
        )

    @server.prompt(
        name="research-topic",
        description="Run deep multi-angle research on a topic using the knowledge base.",
    )
    def research_topic(topic: str) -> str:
        """Run comprehensive deep research on a topic.

        Args:
            topic: The topic to research thoroughly.
        """
        return (
            f"Use the `deep_research` tool to run thorough multi-angle research "
            f"on this topic using the knowledge base: {topic}"
        )
