from config import SearchConfig

# No horsepower field here on purpose - HP filtering was removed.
# The AI stage is responsible for deciding relevance, not a keyword/
# regex parse of the title.
CONFIG = SearchConfig(
    name="Outboard Motors",
    query="outboard motor",
    latitude=39.00,
    longitude=-78.25,
    radius=50,
    database_path="databases/outboard_motors.db",
    negative_keywords=[
        "toy",
        "model",
        "civic",
    ],
)
