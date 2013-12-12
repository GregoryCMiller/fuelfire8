"""Wedge : select grid cell centers within a bearing and distance range. 

includes a test suite"""

import numpy as num
import unittest2 as unittest

def Wedge(radius, start, end, maxdist=None, mindist=None, center=False):
    """Select grid cell centers within a bearing and distance range.
    
    parameters::
            
        radius       Defines side length 2*radius+1. Must be a positive integer.  
        start/end    start/end angle of wedge in degrees counter-clockwise from 3:00. Values outside [0,360) allowed. 
        min/maxdist  minimum/maximum euclidean distance (default=None)
        center       assign value of center cell (default=False)
        
    examples::
    
        circle   Wedge(4, 0, 360, maxdist=4)
        wedge    Wedge(4, 0, 90)
        ring     Wedge(4, 0, 360, mindist = 2, maxdist=4)
        arc      Wedge(4, 0, 90, mindist=2, maxdist=4)
    
    """
    start, end = unwrapPhase(start), unwrapPhase(end)
    ix, iy = num.meshgrid(range(-radius, radius+1), range(-radius, radius+1))
    angle = unwrapPhase(num.rad2deg(num.arctan2(iy, ix)))
    dist = (ix**2 + iy**2)**0.5
    
    if start < end:
        keep = num.bitwise_and(angle >= start, angle <= end)
    else:
        keep = num.bitwise_or(angle >= start, angle <= end)
    
    if maxdist:
        keep = num.bitwise_and(keep, dist <= maxdist)
    if mindist:
        keep = num.bitwise_and(keep, dist >= mindist)
        
    keep[dist==0] = center
    
    return keep

def unwrapPhase(deg):
    """add or subtract 360 until input is 0 <= x < 360"""
    while (deg >= 360):
        deg -= 360
    while (deg < 0):
        deg += 360
    return deg

unwrapPhase = num.vectorize(unwrapPhase)



class TestWedge(unittest.TestCase):
    """Wedge test fixture""" 
    def test_edge(self):
        """test edge cases behave as expected"""
        self.assertRaises(TypeError, Wedge, '2', 0, 0)
        self.assertRaises(TypeError, Wedge, 2, '0', 0)
        
        self.assertEqual(Wedge(-1, 0, 90).shape, (0,0))
        self.assertEqual(Wedge(0, 0, 90).shape, (1,1))
        self.assertEqual(Wedge(1, 0, 90).shape, (3,3))

    def test_quads(self): 
        w_1_0_90    = [[0, 0, 0],
                       [0, 0, 1],
                       [0, 1, 1]]
            
        w_1_90_180  = [[0, 0, 0],
                       [1, 0, 0],
                       [1, 1, 0]]
        
        w_1_180_270 = [[1, 1, 0],
                       [1, 0, 0],
                       [0, 0, 0]]
        
        w_1_270_360 = [[0, 1, 1],
                       [0, 0, 1],
                       [0, 0, 0]]
        
        self.assertTrue(num.all(Wedge(1, 0, 90) == w_1_0_90))    
        self.assertTrue(num.all(Wedge(1, 90, 180) == w_1_90_180))
        self.assertTrue(num.all(Wedge(1, 180, 270) == w_1_180_270))
        self.assertTrue(num.all(Wedge(1, 270, 360) == w_1_270_360))
        
    def test_halves(self):
        w_1_0_180   = [[0, 0, 0],
                       [1, 0, 1],
                       [1, 1, 1]]
        
        w_1_90_270  = [[1, 1, 0],
                       [1, 0, 0],
                       [1, 1, 0]]
        
        w_1_180_360 = [[1, 1, 1],
                       [1, 0, 1],
                       [0, 0, 0]]
        
        w_1_270_90  = [[0, 1, 1],
                       [0, 0, 1],
                       [0, 1, 1]]
        
        self.assertTrue(num.all(Wedge(1, 0, 180) == w_1_0_180))    
        self.assertTrue(num.all(Wedge(1, 90, 270) == w_1_90_270))
        self.assertTrue(num.all(Wedge(1, 180, 360) == w_1_180_360))
        self.assertTrue(num.all(Wedge(1, 270, 90) == w_1_270_90))
        
    def test_negative_angle(self):
        w_1_270_360 = [[0, 1, 1],
                       [0, 0, 1],
                       [0, 0, 0]]
        
        w_1_180_90  = [[1, 1, 1],
                       [1, 0, 1],
                       [0, 1, 1]]
        
        self.assertTrue(num.all(Wedge(1, -90, 0) == w_1_270_360))
        self.assertTrue(num.all(Wedge(1, -180, -270) == w_1_180_90))    
            
    def test_distance(self):
        w_2_0_90_maxd2  = [[0, 0, 0, 0, 0],
                           [0, 0, 0, 0, 0],
                           [0, 0, 0, 1, 1],
                           [0, 0, 1, 1, 0],
                           [0, 0, 1, 0, 0]]
    
        w_2_0_90_mind2  = [[0, 0, 0, 0, 0],
                           [0, 0, 0, 0, 0],
                           [0, 0, 0, 0, 1],
                           [0, 0, 0, 0, 1],
                           [0, 0, 1, 1, 1]]
        
        self.assertTrue(num.all(Wedge(2, 0, 90, maxdist=2) == w_2_0_90_maxd2))
        self.assertTrue(num.all(Wedge(2, 0, 90, mindist=2) == w_2_0_90_mind2))    
   
if __name__ == "__main__":
    #unittest.TextTestRunner(verbosity=2).run(unittest.makeSuite(TestWedge))
    unittest.main()