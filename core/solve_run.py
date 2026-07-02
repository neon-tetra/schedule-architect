from pydantic import BaseModel, model_validator, ConfigDict
from core.frames import INTERVAL_SCHEMA, ROSTER_SCHEMA
import polars as pl

class SolveRun(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    run_id:    str
    label:     str
    intervals: pl.DataFrame
    roster:    pl.DataFrame
    #pydantic config - allow arbitrary types in model_config


    @model_validator(mode="after")
    def validate_frames(self):
        #assert df schemas
        assert self.intervals.schema.keys() == INTERVAL_SCHEMA.keys(), "Interval DataFrame schema mismatch."
        assert self.roster.schema.keys()    == ROSTER_SCHEMA.keys(),   "Roster DataFrame schema mismatch."
  