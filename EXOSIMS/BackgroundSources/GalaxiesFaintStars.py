from EXOSIMS.Prototypes.BackgroundSources import BackgroundSources
import os, inspect
import numpy as np
import astropy.units as u
from astropy.coordinates import SkyCoord
from scipy.interpolate import griddata


class GalaxiesFaintStars(BackgroundSources):
    """
    GalaxiesFaintStars class
    
    This class calculates the total number background sources in number per square 
    arcminute, including galaxies and faint stars. 
    
    """

    def __init__(self, **specs):
        """
        Constructor for class GalaxiesFaintStars
        """
        BackgroundSources.__init__(self, **specs)

    def dNbackground(self, coords, intDepths):
        """
        Return total number counts per square arcmin
        
        Args:
            coords (astropy SkyCoord array):
                SkyCoord object containing right ascension, declination, and 
                distance to star of the planets of interest in units of deg, deg and pc
            intDepths (float ndarray):
                Integration depths equal to the V magnitude (in the detection 
                band) of the dark hole to be produced for each target. it is the
                limiting planet magnitude (faintest planet/objects we can observe),
                which corresponds to dMagLim + Vmag of each specific target.
                Must be of same length as coords.
                
        
        Returns:
            dN (astropy Quantity array):
                Number densities of background sources for given targets in 
                units of 1/arcmin2. Same length as inputs.
        
        """
        
        # check whether inputs are valid arrays
        mag = np.array(intDepths)
        if not mag.shape:
            mag = np.array([mag])
        dN = super(GalaxiesFaintStars, self).dNbackground(coords, mag)
        # make sure mag is within [15,25]
        assert np.all((mag >= 15) & (mag <= 25)), "BackgroundSources input magnitude "\
                "outside range of [15, 25]"
        
        #retrieve the galactic latitude in degrees from input coords
        lat = abs(coords.galactic.b.degree)
        
        # Load stellar background counts from Windhorst11_table.txt
        # The table comes from Windhorst et al 2011 who derived numbers based
        # on Deep Field HST data. Similiar numbers are seen in the CANDELS papers.
        # In this case, the units are in V magnitudes. 
        path = os.path.split(inspect.getfile(self.__class__))[0]
        table = np.loadtxt(os.path.join(path, 'Windhorst11_table.txt'))
        # create data point coordinates
        lat_pts = np.array([0.,5,10,20,30,60,90]) # deg
        mag_pts = np.array([15.,16,17,18,19,20,21,22,23,24,25])
        y_pts,x_pts = np.meshgrid(mag_pts,lat_pts)
        points = np.array(zip(np.concatenate(x_pts),np.concatenate(y_pts)))
        # create data values
        values = table.reshape(table.size)
        # interpolates 2D
        C_st = griddata(points,values,zip(lat,mag)) # log values
        C_st = 10**C_st / 3600
        
        # Galaxy count per square arcmin
        C_gal = 2 * 2.1**(mag - 12.5) / 3600
        
        # total counts
        dN = C_st + C_gal
        
        return dN/u.arcmin**2
