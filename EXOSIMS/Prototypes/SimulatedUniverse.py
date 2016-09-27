import numpy as np
import astropy.units as u
import astropy.constants as const
from EXOSIMS.util.keplerSTM import planSys
from EXOSIMS.util.get_module import get_module
from EXOSIMS.util.eccanom import eccanom
import EXOSIMS.util.statsFun as statsFun 
import numbers

class SimulatedUniverse(object):
    """Simulated Universe class template
    
    This class contains all variables and functions necessary to perform 
    Simulated Universe Module calculations in exoplanet mission simulation.
    
    Args:
        \*\*specs:
            user specified values
    
    Attributes:
        PlanetPopulation (PlanetPopulation module):
            PlanetPopulation class object
        PlanetPhysicalModel (PlanetPhysicalModel module):
            PlanetPhysicalModel class object
        OpticalSystem (OpticalSystem module):
            OpticalSystem class object
        ZodiacalLight (ZodiacalLight module):
            ZodiacalLight class object
        BackgroundSources (BackgroundSources module):
            BackgroundSources class object
        PostProcessing (BackgroundSources module):
            PostProcessing class object
        Completeness (Completeness module):
            Completeness class object
        TargetList (TargetList module):
            TargetList class object
        nPlans (integer):
            Total number of planets
        plan2star (integer ndarray):
            Indices mapping planets to target stars in TargetList
        sInds (integer ndarray):
            Unique indices of stars with planets in TargetList
        a (astropy Quantity array):
            Planet semi-major axis in units of AU
        e (float ndarray):
            Planet eccentricity
        I (astropy Quantity array):
            Planet inclination in units of deg
        O (astropy Quantity array):
            Planet right ascension of the ascending node in units of deg
        w (astropy Quantity array):
            Planet argument of perigee in units of deg
        M0 (astropy Quantity array):
            Initial mean anomaly in units of deg
        p (float ndarray):
            Planet albedo
        Rp (astropy Quantity array):
            Planet radius in units of km
        Mp (astropy Quantity array):
            Planet mass in units of kg
        r (astropy Quantity nx3 array):
            Planet position vector in units of AU
        v (astropy Quantity nx3 array):
            Planet velocity vector in units of AU/day
        s (astropy Quantity array):
            Planet-star apparent separations in units of AU
        d (astropy Quantity array):
            Planet-star distances in units of AU
        fEZ (astropy Quantity array):
            Surface brightness of exozodiacal light in units of 1/arcsec2
        planetTime (astropy Quantity array):
            Contains the last time the planet was observed in units of day, 
            for planet position propagation
    
    Notes:
        PlanetPopulation.eta is treated as the rate parameter of a Poisson distribution.
        Each target's number of planets is a Poisson random variable sampled with \lambda=\eta.
    """

    _modtype = 'SimulatedUniverse'
    _outspec = {}
    
    def __init__(self, **specs):
       
        # import TargetList class
        self.TargetList = get_module(specs['modules']['TargetList'],'TargetList')(**specs)
        
        # bring inherited class objects to top level of Simulated Universe
        TL = self.TargetList
        self.PlanetPopulation = TL.PlanetPopulation 
        self.PlanetPhysicalModel = TL.PlanetPhysicalModel
        self.OpticalSystem = TL.OpticalSystem 
        self.ZodiacalLight = TL.ZodiacalLight 
        self.BackgroundSources = TL.BackgroundSources
        self.PostProcessing = TL.PostProcessing
        self.Completeness = TL.Completeness 
        
        # generate orbital elements, albedos, radii, and masses
        self.gen_planetary_systems(**specs)
        
        # find initial position-related parameters: position, velocity, planet-star 
        # distance, apparent separation, surface brightness of exo-zodiacal light
        self.planet_pos_vel_ez()

    def __str__(self):
        """String representation of Simulated Universe object
        
        When the command 'print' is used on the Simulated Universe object, 
        this method will return the values contained in the object"""
        
        for att in self.__dict__.keys():
            print '%s: %r' % (att, getattr(self, att))
        
        return 'Simulated Universe class object attributes'

    def gen_planetary_systems(self,**specs):
        """
        Generates the planetary systems for the current simulated universe.
        This routine populates arrays of the orbital elements and physical 
        characteristics of all planets, and generates indexes that map from 
        planet to parent star.
        """
        
        PPop = self.PlanetPopulation
        TL = self.TargetList
        
        # Map planets to target stars
        #this version only works for eta < 1
        #probs = np.random.uniform(size=TL.nStars)
        #self.plan2star = np.where(probs > PPop.eta)[0]
        #self.sInds = np.unique(self.plan2star)
        #self.nPlans = len(self.plan2star)
        
        #treat eta as the rate paramter of a Poisson distribution
        targetSystems = np.random.poisson(lam=PPop.eta,size=TL.nStars)
        plan2star = []
        for j,n in enumerate(targetSystems):
            plan2star = np.hstack((plan2star,[j]*n))
        self.plan2star = plan2star.astype(int)
        self.sInds = np.unique(self.plan2star)
        self.nPlans = len(self.plan2star)
        
        #sample all of the orbital and physical parameters
        self.a = PPop.gen_sma(self.nPlans)                  # semi-major axis
        self.e = PPop.gen_eccen_from_sma(self.nPlans,self.a) if PPop.constrainOrbits \
                else PPop.gen_eccen(self.nPlans)            # eccentricity
        self.I = PPop.gen_I(self.nPlans)                    # inclination
        self.O = PPop.gen_O(self.nPlans)                    # longitude of ascending node
        self.w = PPop.gen_w(self.nPlans)                    # argument of periapsis
        self.M0 = np.random.uniform(360,size=self.nPlans)*u.deg # initial mean anomaly
        self.Rp = PPop.gen_radius(self.nPlans)              # radius
        self.Mp = PPop.gen_mass(self.nPlans)                # mass
        self.p = PPop.gen_albedo(self.nPlans)               # albedo

    def planet_pos_vel_ez(self):
        """
        Finds initial position-related parameters. Assigns each planet an initial 
        position (AU), velocity (AU/day), planet-star distance (AU), apparent separation 
        (AU), surface brightness of exo-zodiacal light (1/arcsec2) by calling the 
        ZodiacalLight module, and the planetTime array. This method makes us of the 
        planet orbital elements (a, e, I, O, w, M0), and the planet and star masses.
        """
        
        a = self.a.to('AU').value               # semi-major axis
        e = self.e                              # eccentricity
        I = self.I.to('rad').value              # inclinations
        Omega = self.O.to('rad').value          # right ascension of the ascending node
        w = self.w.to('rad').value              # argument of perigee
        M0 = self.M0.to('rad').value            # initial mean anomany
        E = eccanom(M0, e)                      # eccentric anomaly
        Mp = self.Mp                            # planet masses
        Ms = self.TargetList.MsTrue[self.plan2star] # target star masses
        
        a1 = np.cos(Omega)*np.cos(w) - np.sin(Omega)*np.cos(I)*np.sin(w)
        a2 = np.sin(Omega)*np.cos(w) + np.cos(Omega)*np.cos(I)*np.sin(w)
        a3 = np.sin(I)*np.sin(w)
        A = a*np.vstack((a1,a2,a3))*u.AU
        b1 = -np.sqrt(1.-e**2)*(np.cos(Omega)*np.sin(w) + np.sin(Omega)*np.cos(I)*np.cos(w))
        b2 = np.sqrt(1.-e**2)*(-np.sin(Omega)*np.sin(w) + np.cos(Omega)*np.cos(I)*np.cos(w))
        b3 = np.sqrt(1.-e**2)*np.sin(I)*np.cos(w)
        B = a*np.vstack((b1,b2,b3))*u.AU
        
        r1 = np.cos(E) - e
        r2 = np.sin(E)
        mu = const.G*(Mp + Ms*const.M_sun)
        v1 = np.sqrt(mu/self.a**3)/(1. - e*np.cos(E))
        v2 = np.cos(E)
        
        self.r = (A*r1 + B*r2).T.to('AU')                       # position
        self.v = (v1*(-A*r2 + B*v2)).T.to('AU/day')             # velocity
        self.d = np.sqrt(np.sum(self.r**2, axis=1))             # planet-star distance
        self.s = np.sqrt(np.sum(self.r[:,0:2]**2, axis=1))      # apparent separation
        # surface brightness of exo-zodiacal light
        self.fEZ = self.ZodiacalLight.fEZ(self.TargetList,self.plan2star,self.I,self.d)
        # current time (normalized to zero at mission start) of planet positions
        self.planetTime = np.zeros(self.nPlans)*u.day

    def prop_system(self, sInd, currentTimeNorm):
        """Propagates planet state vectors (position, velocity) and updates all
        position-related parameters: position (AU), velocity (AU/day), planet-star distance (AU), apparent separation 
        (AU), surface brightness of exo-zodiacal light (1/arcsec2), and the
        planetTime array.
        
        This method uses the Kepler state transition matrix to propagate a 
        planet's state (position and velocity vectors) forward in time using 
        the Kepler state transition matrix.
        
        Args:
            sInd (integer):
                Index of the target system of interest
            currentTimeNorm (astropy Quantity):
                Current mission time normalized to zero at mission start in units of day
        
        """
        
        # planet indices
        assert np.isscalar(sInd), "Can only propagate one system at a time, \
                sInd must be scalar."
        pInds = np.where(self.plan2star == sInd)[0]
        # calculate time increment
        dt = currentTimeNorm - self.planetTime[pInds][0]
        assert dt >= 0, "Time increment (dt) to propagate a planet must be positive."
        if dt == 0:
            return
        
        # Initial positions in AU and velocities in AU/day
        rold = self.r[pInds].to('AU').value
        vold = self.v[pInds].to('AU/day').value
        # stack dimensionless positions and velocities
        x0 = np.array([])
        for i in xrange(len(rold)):
            x0 = np.hstack((x0, rold[i], vold[i]))
        
        # calculate target star masses in M_sun
        sInds = self.plan2star[pInds]
        Ms = self.TargetList.MsTrue[[sInd]]
        # calculate vector of gravitational parameter
        mu = (const.G*(self.Mp[pInds] + Ms*const.M_sun)).to('AU3/day2').value
        
        # use keplerSTM.py to propagate the system
        prop = planSys(x0, mu, epsmult=10.)
        try:
            prop.takeStep(dt.to('day').value)
        except ValueError:
            #try again with larger epsmult and two steps to force convergence 
            prop = planSys(x0, mu, epsmult=100.)
            try:
                prop.takeStep(dt.to('day').value/2.)
                prop.takeStep(dt.to('day').value/2.)
            except ValueError:
                raise ValueError('planSys error')
        
        # split off position and velocity vectors
        x1 = np.array(np.hsplit(prop.x0, 2*len(rold)))
        rind = np.array(range(0,len(x1),2)) # even indices
        vind = np.array(range(1,len(x1),2)) # odd indices
        
        # update planets' position, velocity, apparent separation, planet-star 
        # distance, exo-zodiacal surface brightness, and times
        self.r[pInds] = x1[rind]*u.AU
        self.v[pInds] = x1[vind]*u.AU/u.day
        self.s[pInds] = np.sqrt(np.sum(self.r[pInds,0:2]**2, axis=1))
        self.d[pInds] = np.sqrt(np.sum(self.r[pInds]**2, axis=1))
        self.fEZ[pInds] = self.ZodiacalLight.fEZ(self.TargetList,sInd,self.I[pInds],self.d[pInds])
        self.planetTime[pInds] = currentTimeNorm
