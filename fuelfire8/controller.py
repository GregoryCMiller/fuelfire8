"""classes for controlling, recording runs, and recording replicate runs on the FUELFIRE8 model"""

import logging
import os
import shutil
import subprocess
import time
import win32com.client

import numpy as num
from netCDF4 import Dataset

try:
    import scipy.ndimage
except ImportError:
    pass
    
    
from fuelfire8 import ConfigFile, GetFootprint, Wedge

NETCDF_FORMAT = 'NETCDF3_CLASSIC'

logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger().addHandler(logging.FileHandler('log.txt'))
SHELL = win32com.client.Dispatch("WScript.Shell")

def PropegateModel(dst, src=None, copyrecord=False, copyrepeats=False,
                   modif=None, caption=None, 
                   spinup=0, recordlength=None, runrecord=0, 
                   repeatlength=None, runrepeats=(0,0), stepoffset=0 
                   ):
    """create a new record from an existing one. specify which data files are copied or reset. 
    
    dst           
        Destination folder or target model
    
    src
        Source folder, empty or None if not copying 
    
    copyrecord
        copy the RecordedFuelFire data file when copying the model.
        
    copyrepeats
        copy the RepeatedFuelFire data file when copying the model.
        
    modif         
        Configuration modifications list (see fuelfire8.EditConfig)
    
    caption       
        Created model caption parameter
    
    spinup        
        Run <spinup> number of steps before beginning to record steps
    
    recordlength  
        Initialize (or reset) RecordedFuelFire data file with
        <recordlength> time steps
    
    runrecord     
        Run RecordedFuelFire forward steps until a total of <runrecord>
        steps are completed
    
    repeatlength  
        Initialize RepeatedFuelFire data file specififying storage for
        <repeatlength> replicates of each step
    
    runrepeats    
        Run the RepeatedFuelFire to <replicates> replicates of <steps>
        steps
    
    stepoffset:
        Temporarily add <stepoffset> to the list of shuffled steps.
        choose 1 to run the second of pairs of steps.
    
    """
    if src is not None:
        CopyModel(src, dst, record=copyrecord, repeat=copyrepeats)
    
    if modif is not None and caption is not None:
        FuelFire(dst).EditConfig(modif,caption)

    if spinup > 0:
        FuelFire(dst).StraightSteps(spinup)

    if recordlength is not None:
        RecordedFuelFire(dst, recordlength)

    if runrecord > 0:
        RecordedFuelFire(dst).RunSteps(runrecord)
    
    if repeatlength is not None:
        RepeatedFuelFire(dst, maxreps=repeatlength,stepoffset=stepoffset)

    if runrepeats[0] > 0 and runrepeats[1] > 0:
        RepeatedFuelFire(dst).RunReps(runrepeats[0],runrepeats[1])
    

class FuelFire:
    """Controller for a FuelFire model with methods for starting,
    stopping, timed run, run x steps, clear temp data"""
    # controller time constants in seconds 
    LAUNCHWAIT  = 1     # while FF_EXE launches before dialog exit
    ACCESSSLEEP = 2     # while file cannot be accessed
    MODTHRESH   = 2     # modification time threshold
    MODSLEEP    = 0.5   # between checks for modification thresh
    POLLSLEEP   = 0.5   # between checks for poll response
    WAITTIMEOUT = 180   # timeout for model.wait()
    KILLTIMEOUT = 20    # timeout for model.kill()
    
    def __init__(self, ffdir):
        self.ffdir    = ffdir
        self.burnfile = os.path.join(self.ffdir, 'BURNT0OUT.TXT')
        self.config   = os.path.join(self.ffdir, 'FUELFIRE.CFG')
        self.exefile  = os.path.join(self.ffdir, 'FUELFIRE.EXE')
        self.agefile  = os.path.join(self.ffdir, 'AGEPIX.DAT')
        self.fuelfile = os.path.join(self.ffdir, 'CANOPIX.DAT')

        # instance variables initialized later
        #   status      False if something went wrong during this step 
        #   starttime   time model was started
        #   FF_EXE      subprocess instance 
        #   burndata    loaded burned pixel matrix from this step
        
    def EditConfig(self, modlist, caption):
        """Use the EditConfig module modify the config file"""
        cf = ConfigFile(self.config)
        cf.PresetModify(modlist,caption)
        logging.info('modified '+str(modlist))
    
    def TimedRun(self, holdmin):
        """Run the FUELFIRE normally (for spin-up). remove the sequence of files."""
        logging.info('Timed Run (%d min)' % holdmin)
        self.StartModel()
        time.sleep(holdmin * 60)
        self.Kill()
        self.RemoveBurn()
        
    def StraightSteps(self, maxstep, checkint=60,printinc=20):
        """run forward steps. """
        logging.info('%d straight steps' % maxstep)
        while 1:            
            self.RemoveBurn()
            self.StartModel()
            self.ModelWait(fatalerror=False)
            if self.status:
                marks = range(0,maxstep,printinc)
                while len(marks) > 0:
                    if os.path.exists('BURNT%dOUT.TXT' % marks[0]):
                        logging.info('completed %d steps' % marks[0])
                        marks.pop(0)

                    time.sleep(checkint)
                
            self.Kill()
            self.RemoveBurn()    
            
            if self.status:
                logging.info('completed')
                return 
            else:
                logging.info('retry single steps')
                     
    def SingleStep(self,fatal=False):
        """Run a single model step"""
        self.StartModel()
        self.ModelWait(fatalerror=fatal)
        self.Kill()
        self.burndata = self.GetBout()
        
    def StartModel(self):
        """Start the fuelfire model"""
        os.chdir(self.ffdir)
        if os.path.exists(self.burnfile):
            os.remove(self.burnfile)

        self.burndata = None
        self.status = True
        self.starttime = time.time()
        self.FF_EXE = subprocess.Popen(self.exefile, shell=False)      
        time.sleep(self.LAUNCHWAIT)
        SHELL.SendKeys('{ESC}')

    def ModelWait(self, fatalerror=True):
        """Wait for the running model to write the BURNOUT file"""
        while time.time() - self.starttime < self.WAITTIMEOUT:
            if os.access(self.burnfile, os.R_OK) == False:
                time.sleep(self.ACCESSSLEEP)
                #log.debug('Waiting for file...')
            else:
                bstat = os.stat(self.burnfile)
                if time.time() - bstat[-3] > self.MODTHRESH: #if one sec without mod
                    return True
                else:
                    #log.debug('Waiting for mod')
                    time.sleep(self.MODSLEEP)

        logging.warning('Wait Timeout')    
        self.status = False
        return False

    def Kill(self):
        """Kill any running FUELFIRE threads using the process name"""
        f = open('execlog.txt', 'w')
        starttime = time.time()
        SHELL.SendKeys('{ESC}')
        SHELL.SendKeys('^S')
        while not self.FF_EXE.poll():
            p = subprocess.Popen('TASKKILL '+'/IM '+'FUELFIRE.EXE' +' /F', stderr=f, stdout=f, shell=True)
            while not p.poll():
                time.sleep(self.POLLSLEEP)

        f.close()
        os.remove('execlog.txt')
        os.chdir(self.ffdir)
        if time.time() - starttime < self.KILLTIMEOUT:
            self.steptime = str(int(time.time() - self.starttime))
            return True
        else:
            logging.error('Kill Timeout')
            self.status = False
            return

    def GetBout(self):    
        """Read the burnt output file """
        retval = None
        if self.status == True and os.access(self.burnfile, os.F_OK):
            retval = num.array(num.loadtxt(self.burnfile, skiprows=6), dtype='i') 
            retval = retval <= 0
            
        return retval
        
    def RemoveBurn(self):
        """remove all BURNT<n>OUT.TXT files"""
        
        n = 0
        while 1:
            f = os.path.join(self.ffdir,'BURNT%dOUT.TXT' % n)
            if not os.path.exists(f):
                break
            
            os.remove(f)
            n += 1
                
class RecordedFuelFire:
    """Run and record a sequence of FUELFIRE model steps saving age,
    fuel, and steps completed to a NetCDF file
    
    
    must specify the total number of steps stored at creation 
    
    Data file variables (dimensions)
    --------------------------------
    
    age (txy)   
        time since fire in model steps (0-255 stored as x-128)
    
    fuel (txy)
        fuel level (0-255 stored as x-128)
    
    complete (t)
        step status 0|1
    
    shufsteps (t)
        randomly ordered step index (inhereted by replication experiments)
        
    """
    def __init__(self, ffdir, maxsteps=None):
        """Load existing record or create empty record"""
        self.ff = FuelFire(ffdir)
        self.ncfile = os.path.join(ffdir, 'record.nc')
        
        if os.path.exists(self.ncfile):
            self.nc = Dataset(self.ncfile,'a')
            
        if (not os.path.exists(self.ncfile)) & (maxsteps != None):
            self.CreateEmptyRecord(maxsteps)
            self.nc = Dataset(self.ncfile,'a')
        
        if (not os.path.exists(self.ncfile)) & (maxsteps == None):
            raise StandardError('file not found {0}'.format(self.ncfile))    
    
    def CreateEmptyRecord(self, steps):
        """create and empty record of age and fuel"""
        (xlen, ylen) = num.loadtxt(self.ff.agefile).shape
        
        self.nc = Dataset(self.ncfile, 'w', format=NETCDF_FORMAT)
        self.nc.createDimension('t', steps)
        self.nc.createDimension('x', xlen)
        self.nc.createDimension('y', ylen)
        
        age = self.nc.createVariable('age', 'i1', ('t','x','y',))
        fuel = self.nc.createVariable('fuel', 'i1', ('t','x','y',))
        complete = self.nc.createVariable('complete', 'i1', ('t',))
        shufsteps = self.nc.createVariable('shufsteps', 'i2', ('t',))
        
        age[:,:,:] = -128
        fuel[:,:,:] = -128
        complete[:] = 0
        steplist = num.arange(steps)
        num.random.shuffle(steplist)
        shufsteps[:] = steplist
        
        self.SaveMosaic(0)    
    
    def RunSteps(self, stop=None):
        """run forward steps up to <stop>"""
        steps = num.where(self.nc.variables['complete'][:] == 0)[0]
        if stop != None:
            steps = steps[steps <= stop]
        
        while steps.shape[0] > 0:
            step = steps[0]
            self.ReLoadMosaic(step-1)
            self.ff.SingleStep()
            if self.ff.status == True:
                self.SaveMosaic(step)
                if self.ff.status == True:
                    logging.info('completed step %d' % step)
                    steps = steps[1:]
            else:
                logging.info('retry step %d' % step)
        
        logging.info('Run Steps: completed %s' % os.path.basename(self.ff.ffdir))
            
    def SaveMosaic(self, step):
        """save the current age and fuel arrays to the netcdf file"""
        age = -127 + num.loadtxt(self.ff.agefile, dtype='i')
        fuel = -127 + num.loadtxt(self.ff.fuelfile, dtype='i')
        if step > 0:
            agediff = age - (self.nc.variables['age'][step-1, :, :])
            if num.mean(agediff == 0) > 0.5:
                logging.warning('ERROR: mosaic is same as previous step')
                self.ff.status = False
                return False
            
        self.nc.variables['age'][step, :, :] = age 
        self.nc.variables['fuel'][step, :, :] = fuel 
        self.nc.variables['complete'][step] = 1
        self.nc.sync()
        logging.debug('saved step %d' % step)

    def ReLoadMosaic(self, step):
        """write age and fuel data from <step> to the current fuelfire text data files"""
        num.savetxt(self.ff.agefile, 127 + self.nc.variables['age'][step, :, :], fmt='%4i')
        num.savetxt(self.ff.fuelfile, 127 + self.nc.variables['fuel'][step, :, :], fmt='%4i')
        logging.debug('reloaded mosaic %d' % step) 

        
class RepeatedFuelFire:
    """Run and store replicate trials from a RecordedFuelFire experiment
    
    Data file variables (dimensions)
    --------------------------------
    
    steps (t)
        sequential step number of replicated landscape
    
    repvar (t)
        number of replicates so far        
    
    trials (rtxy)
        bitpacked binary burned pixels from each replicate trial
    
    age (txy)
        time since fire in model steps
    
    fuel (txy)
        fuel level
    
    haz (txy)
        number of times burned
    
    reach (txy)
        number of times reached (within neighborhood filter of burned 
    
    burnifreach (txy)   
        number of times burned and reached
    
    """
    def __init__(self, ffdir, maxreps=None, stepoffset=None,footprintcode='5ne',calcint=32):
        """load or create empty RepeatedFuelFire data"""
        self.rec = RecordedFuelFire(ffdir)
        self.repfile = os.path.join(ffdir, 'repeat.nc')
        
        if not os.path.exists(self.repfile) and maxreps is not None:
            self.CreateEmptyRecord(maxreps, stepoffset)
        elif os.path.exists(self.repfile) and maxreps is None:
            self.rep = Dataset(self.repfile,'a')
        
        self.footprintcode = footprintcode
        self.calcint = calcint
        
    def CreateEmptyRecord(self, reps, stepoffset):
        """create a new empty record. the number of repeats be specified
        but the number of mosaic steps analyzed can grow dynamically"""
        self.rep = Dataset(self.repfile, 'w', format=NETCDF_FORMAT)
        self.rep.stepoffset = stepoffset
        self.rep.createDimension('t', None)
        self.rep.createDimension('r', num.ceil(reps/8.0))
        self.rep.createDimension('x', len(self.rec.nc.dimensions['x']))
        self.rep.createDimension('y', len(self.rec.nc.dimensions['y']))
        
        steps = self.rep.createVariable('step', 'i2', ('t',))
        steps.description = 'original step number'
        
        repvar = self.rep.createVariable('reps', 'i2', ('t',))
        repvar.description = 'repeats per step'
        
        trials = self.rep.createVariable('trials', 'i1', ('t','r','x','y',))
        trials.description = 'bitpacked repeat trials results'
        
        age = self.rep.createVariable('age', 'i1', ('t','x','y',))
        age.description = 'time since fire in model steps'

        fuel = self.rep.createVariable('fuel', 'i1', ('t','x','y',))
        fuel.description = 'fuel'

        haz = self.rep.createVariable('hazard', 'i2', ('t','x','y',))
        haz.description = 'burned'
        
        reach = self.rep.createVariable('reached', 'i2', ('t','x','y',))
        reach.description = 'reached'
        
        burnifreach = self.rep.createVariable('burnifreach', 'i2', ('t','x','y',))
        burnifreach = 'burned and reached'
        
    def RunReps(self, reps=None, steplim=None):
        """run <reps> replicated trials on steps up to <steplim> or"""
        if reps == None:
            reps = 8 * len(self.rep.dimensions['r'])    
        if steplim == None:
            steplim = len(self.rec.nc.dimensions['t'])
            
        for i, step in enumerate(self.rec.nc.variables['shufsteps'][:steplim]):
            xstep = step + self.rep.stepoffset
            if xstep > num.max(self.rec.nc.variables['shufsteps']):
                xstep = 0
                
            if self.rec.nc.variables['complete'][xstep] == 1:
                if len(self.rep.variables['step'][:]) == i:
                    self.rep.variables['step'][i] = xstep
                    self.rep.variables['reps'][i] = 0
                    self.rep.variables['trials'][i,:,:,:] = -127                
                
                xstep = self.rep.variables['step'][i]
                    
                while self.rep.variables['reps'][i] < reps:
                    self.rec.ReLoadMosaic(xstep)
                    self.rec.ff.SingleStep()
                    if (self.rec.ff.status == True) & (type(self.rec.ff.burndata) != type(None)):
                        self.SaveRepeatStep(i, self.rec.ff.burndata)
                        logging.info('saved step %d (%d) %d reps (%d) %s sec %s' % (i, xstep, reps, self.rep.variables['reps'][i], self.rec.ff.steptime, os.path.basename(self.rec.ff.ffdir)))
                        if num.mod(self.rep.variables['reps'][i], self.calcint) == 0: 
                            self.StepProbabilities(i, step)
                
                #logging.info('completed step %d (%d) %d reps (%d) %s' % (i, step, reps, self.rep.variables['reps'][i], os.path.basename(self.rec.ff.ffdir)))
    
    def SaveRepeatStep(self, step, burn):
        """save one replicate. binary data is packed into (m,n,8) blocks of integers"""
        i = int(num.floor(self.rep.variables['reps'][step]/8.0))
        im = num.mod(self.rep.variables['reps'][step],8)
        
        pack = num.array(127 + self.rep.variables['trials'][step, i, :, :], dtype='uint8')
        pack.resize((1, pack.shape[0], pack.shape[1]))
        unpack = num.unpackbits(pack, axis=0)
        unpack[im, :, :] = burn
        
        self.rep.variables['trials'][step,i,:,:] = -127 + num.packbits(unpack, axis=0)
        self.rep.variables['reps'][step] += 1
        self.rep.sync()
            
    def UpdateStepProbs(self, steplim=None,maxreps=256):
        """recalculate step probabilities for every step"""
        if steplim == None:
            steplim = self.rep.variables['reps'].shape[0]
            
        for s, step in enumerate(self.rec.nc.variables['shufsteps'][:steplim]):
            self.StepProbabilities(s,step,maxreps)
            
    def StepProbabilities(self, s, step, maxreps=256):
        """calculate the probability of 
            being reached by fire at a specified radius.
            catching fire if reached  
            
        """
        print('probs')
        reps = self.rep.variables['reps'][s]
        if reps > maxreps:
            reps = maxreps

        blockreps = int(num.ceil(reps/8.0))
            
        self.rep.variables['age'][s,:,:] = self.rec.nc.variables['age'][step,:,:]
        self.rep.variables['fuel'][s,:,:] = self.rec.nc.variables['fuel'][step,:,:]
        footprint = GetFootprint(self.footprintcode)
            
        # probability of being reached
        trials = num.unpackbits(num.array(127 + self.rep.variables['trials'][s, :blockreps, :, :], dtype='uint8'), axis=0)
        self.rep.variables['hazard'][s,:,:] = num.sum(trials, axis=0)
        self.rep.variables['reached'][s,:,:] = 0
        self.rep.variables['burnifreach'][s,:,:] = 0
        for i in num.arange(reps):
            zz = scipy.ndimage.maximum_filter(trials[i,:,:], footprint=footprint)
            self.rep.variables['reached'][s,:,:] += zz
            self.rep.variables['burnifreach'][s,:,:] += num.bitwise_and(trials[i,:,:], zz)
        
        self.rep.sync()
        print 'step probs %d (%d reps)' % (s, reps)
           
def CopyModel(src, dst,repeat=False,record=False):
    """copy all relevant model files from <src> to <dest> with options for copying recorded and repeated data files"""
    if os.path.exists(dst):
        shutil.rmtree(dst)
    if not os.path.exists(dst):
        os.makedirs(dst)
    
    files = ['FUELFIRE.EXE','FUELFIRE.CFG','CANOPIX.DAT','AGEPIX.DAT']
    
    if record and os.path.exists(os.path.join(src, 'record.nc')):
        files.append('record.nc')
        
    if repeat and os.path.exists(os.path.join(src, 'repeat.nc')):
        files.append('repeat.nc')
    
    [shutil.copy(os.path.join(src, f), os.path.join(dst, f)) for f in files]
    
    logging.info('Copied to %s' % dst)
    
def QuickUpdateProbs(path, footprintcode='7ne',maxreps=160):
    """Recalculate derived step probabilities given an input footprint code string"""
    RepeatedFuelFire(path, footprintcode=footprintcode).UpdateStepProbs(maxreps=maxreps)
    return True

def NewFilterVar(nc, srcvar, tarvar, footprint, dtype='i',dim=('t','x','y')):
    """create a new xyt variable by applying a median filter each step slice of an existing xyt variable"""
    print('New Filter Variable: {0} from {1}'.format(tarvar, srcvar))
    if srcvar not in nc.variables:
        raise StandardError('source var {0} not found'.format(srcvar))
    
    if tarvar not in nc.variables:
        newvar = nc.createVariable(tarvar, dtype, dim)
        nc.sync()
        print('add var {0}'.format(tarvar))
    
    for step in num.arange(len(nc.dimensions['t'])):
        nc.variables[tarvar][step,:,:] = scipy.ndimage.median_filter(nc.variables[srcvar][step,:,:], footprint=footprint)
        print('{0}'.format(step))
    
def AddNeighbors(path, footprintcode='3sw', stepoffset=None):
    """create and/or recalculate a median age variable""" 
    print('calculate neighborhood age')
    rec = RecordedFuelFire(path)
    ff = RepeatedFuelFire(path)
    if 'hoodmed' not in ff.rep.variables:
        hoodmed = ff.rep.createVariable('hoodmed', 'i1', ('t','x','y',))
        hoodmed.description = 'median age in neighborhood'
        ff.rep.sync()

    for s, step in enumerate(ff.rep.variables['step'][:]):    
        ff.rep.variables['hoodmed'][s, :, :] = scipy.ndimage.median_filter(rec.nc.variables['age'][step, :, :], footprint=GetFootprint(footprintcode))
        
        print step
        
    ff.rep.sync()

def FixAge(path, stepoffset):
    """Recopy the age and fuel data from replicate model to fix a previous copying error""" 
    print('fix age')
    rec = RecordedFuelFire(path)
    ff = RepeatedFuelFire(path)
    ff.rep.variables['step'][:] = rec.nc.variables['shufsteps'][0:len(ff.rep.variables['step'][:])] + stepoffset
    ff.rep.sync()
    
    for s, step in enumerate(ff.rep.variables['step'][:]):
        ff.rep.variables['age'][s, :, :] = rec.nc.variables['age'][step, :, :]
        ff.rep.variables['fuel'][s, :, :] = rec.nc.variables['fuel'][step, :, :]
        print step
    
    
def ChangeMosaic(ffdir, agesrc, fuelsrc):
    """swap out the mosaic age and fuel data files"""
    ff = FuelFire(ffdir)
    age = num.array(num.loadtxt(os.path.join(ffdir,agesrc), delimiter=','), dtype='i')
    fuel = num.array(num.loadtxt(os.path.join(ffdir,fuelsrc), delimiter=','), dtype='i')
    num.savetxt(ff.agefile, num.transpose(age), fmt='%4i')
    num.savetxt(ff.fuelfile, num.transpose(fuel), fmt='%4i')
    