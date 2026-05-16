from pydantic import BaseModel, Field


class ScoreRequest(BaseModel):
    profile: str = Field(default="residential_homestead")
    weights: dict[str, float] | None = None
    limit: int = Field(default=100, ge=1, le=1000)


class RankRequest(BaseModel):
    profile: str = Field(default="residential_homestead")
    weights: dict[str, float] | None = None

    min_score: float | None = None
    min_area_acres: float | None = None
    max_floodplain_pct: float | None = None
    max_wetland_pct: float | None = None
    max_avg_slope_pct: float | None = None
    max_distance_to_road_m: float | None = None
    max_distance_to_town_km: float | None = None
    stream_present: bool | None = None

    limit: int = Field(default=100, ge=1, le=1000)
