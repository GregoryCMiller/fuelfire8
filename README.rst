fuelfire8
=========

helpers for FUELFIRE8 coupled fire and vegetation simulation.

PropegateModel
    Copy an existing model with options to handle data files, modify 
    configuration, run spinup, "record", or "repeat" procedures.

FuelFire
    Controller for a FuelFire model with methods for starting, stopping,
    timed run, run steps, clean temp files.

RecordedFuelFire
    Run and record a sequence of FUELFIRE model steps saving age, fuel,
    and steps completed to a NetCDF file.

RepeatedFuelFire
    Run and store replicate trials pulled from a RecordedFuelFire
    experiment.

ConfigFile
    FUELFIRE configuration file with methods to read, write, and edit
    parameters.

Wedge
    Select grid cell centers within a bearing and distance range
    [circle, wedge, ring, arc].


If you are interested in the model email gmill002@gmail.com
