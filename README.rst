fuelfire8
=========

helpers for FUELFIRE8 coupled fire and vegetation simulation

:FuelFire:
    Controller for a FuelFire model with methods for starting, stopping, timed run, run steps, clean temp files.

:RecordedFuelFire:
    Run and record a sequence of FUELFIRE model steps saving age, fuel, and steps completed to a NetCDF file.
    
:RepeatedFuelFire:
    Run and store replicate trials from a RecordedFuelFire experiment. 

:PropegateModel:
    Create a new model from an existing one. Options for editing config, spinup, copy existing recorded and repeated data.

:ConfigFile:
    FUELFIRE configuration file with methods to read, edit, and write parameters. 
    
:Wedge:
    Select grid cell centers within a bearing and distance range [circle, wedge, ring, arc].
    
