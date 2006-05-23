"""Parser for basic PDB file format

Ref.: http://www.rcsb.org/pdb/docs/format/pdbguide2.2/guide2.2_frame.html
"""

__id__ = "$Id$"

import sys
from Structure.structure import Structure, InvalidStructureFormat
from Structure.lattice import Lattice
from Structure.atom import Atom
from StructureParser import StructureParser
import numarray as num
import numarray.linear_algebra as numalg
from numarray import pi

orderOfRecords = [
    "HEADER", "OBSLTE", "TITLE", "CAVEAT", "COMPND", "SOURCE", "KEYWDS",
    "EXPDTA", "AUTHOR", "REVDAT", "SPRSDE", "JRNL", "REMARK", "REMARK",
    "REMARK", "REMARK", "DBREF", "SEQADV", "SEQRES", "MODRES", "HET",
    "HETNAM", "HETSYN", "FORMUL", "HELIX", "SHEET", "TURN", "SSBOND",
    "LINK", "HYDBND", "SLTBRG", "CISPEP", "SITE", "CRYST1", "ORIGX1",
    "ORIGX2", "ORIGX3", "SCALE1", "SCALE2", "SCALE3", "MTRIX1",
    "MTRIX2", "MTRIX3", "TVECT", "MODEL", "ATOM", "SIGATM", "ANISOU",
    "SIGUIJ", "TER", "HETATM", "ENDMDL", "CONECT", "MASTER", "END",
]
validRecords = dict( zip(orderOfRecords, len(orderOfRecords)*[True]) )

# Parsed records:
#   TITLE CRYST1 SCALE1 SCALE2 SCALE3 ATOM
#   SIGATM ANISOU SIGUIJ TER HETATM END

class Parser(StructureParser):
    """Parser --> StructureParser subclass for basic PDB format"""

    def __init__(self):
        self.format = "pdb"
        return

    def parseLines(self, lines):
        """parse list of lines in PDB format

        return Structure object or raise InvalidStructureFormat exception
        """
        try:
            stru = Structure()
            scale = num.identity(3, type=num.Float)
            scaleU = num.zeros(3, type=num.Float)
            p_nl = 0
            for line in lines:
                # make sure line has 80 characters
                if len(line) < 80:
                    line = "%-80s" % line
                p_nl += 1
                words = line.split()
                record = words[0]
                if record == "TITLE":
                    continuation = line[8:10]
                    if continuation.strip():
                        stru.title += line[10:].rstrip()
                    else:
                        stru.title = line[10:].rstrip()
                elif record == "CRYST1":
                    a = float(line[7:15])
                    b = float(line[15:24])
                    c = float(line[24:33])
                    alpha = float(line[33:40])
                    beta = float(line[40:47])
                    gamma = float(line[47:54])
                    stru.lattice.setLatPar(a, b, c, alpha, beta, gamma)
                    scale = num.transpose(stru.lattice.recbase)
                elif record == "SCALE1":
                    sc = num.zeros(3, type=num.Float)
                    sc[0,:] = [float(x) for x in line[10:40].split()]
                    scaleU[0] = float(line[45:55])
                elif record == "SCALE2":
                    sc[1,:] = [float(x) for x in line[10:40].split()]
                    scaleU[1] = float(line[45:55])
                elif record == "SCALE3":
                    sc[2,:] = [float(x) for x in line[10:40].split()]
                    scaleU[2] = float(line[45:55])
                    den = num.maximum(num.abs(sc), num.abs(scale))
                    den[den==0] = 1.0
                    reldiff = num.abs( (sc - scale)/den )
                    if not num.all(reldiff < 1.0e-4):
                        raise InvalidStructureFormat, ( "%d: SCALE and " +
                                "CRYST1 records are inconsistent." ) % p_nl
                elif record in ("ATOM", "HETATM"):
                    name = line[12:16].strip()
                    rc = [float(x) for x in line[30:54].split()]
                    xyz = num.dot(scale, rc) + scaleU
                    try:
                        occupancy = float(line[54:60])
                    except ValueError:
                        occupancy = 1.0
                    try:
                        B = float(line[60:66])
                        U = num.identity(3)*B/(8*pi**2)
                    except ValueError:
                        U = num.zeros((3,3), type=num.Float)
                    element = line[76:78].strip()
                    if element == "":
                        element = line[12:14].strip()
                        element = element[0].upper() + element[1:].lower()
                    last_atom = Atom(element, xyz,
                            occupancy=occupancy, name=name, U=U)
                    stru.append(last_atom)
                elif record == "SIGATM":
                    sigrc = [float(x) for x in line[30:54].split()]
                    sigxyz = num.dot(scale, sigrc)
                    try:
                        sigo = float(line[54:60])
                    except ValueError:
                        sigo = 0.0
                    try:
                        sigB = float(line[60:66])
                        sigU = num.identity(3)*sigB/(8*pi**2)
                    except ValueError:
                        sigU = num.zeros((3,3), type=num.Float)
                    last_atom.sigxyz = sigxyz
                    last_atom.sigo = sigo
                    last_atom.sigU = sigU
                elif record == "ANISOU":
                    Uij = [ float(x)*1.0e-4 for x in line[28:70].split() ]
                    for i in range(3):
                        last_atom.U[i,i] = Uij[i]
                    last_atom.U[0,1] = last_atom.U[1,0] = Uij[3]
                    last_atom.U[0,2] = last_atom.U[2,0] = Uij[4]
                    last_atom.U[1,2] = last_atom.U[2,1] = Uij[5]
                elif record == "SIGUIJ":
                    sigUij = [ float(x)*1.0e-4 for x in line[28:70].split() ]
                    for i in range(3):
                        last_atom.sigU[i,i] = sigUij[i]
                    last_atom.sigU[0,1] = last_atom.sigU[1,0] = sigUij[3]
                    last_atom.sigU[0,2] = last_atom.sigU[2,0] = sigUij[4]
                    last_atom.sigU[1,2] = last_atom.sigU[2,1] = sigUij[5]
                elif record in validRecords:
                    pass
                else:
                    raise InvalidStructureFormat, \
                            "%d: invalid record name '%r'" % (p_nl, record)
        except (ValueError, IndexError):
            exc_type, exc_value, exc_traceback = sys.exc_info()
            raise InvalidStructureFormat, "%d: file is not in PDB format" % \
                    p_nl, exc_traceback
        return stru
    # End of parseLines

    def titleLines(self, stru):
        """build lines corresponding to TITLE record"""
        lines = []
        title = stru.title
        while title != "":
            stop = len(title)
            # maximum length of title record is 60
            if stop > 60:
                stop = title.rfind(' ', 10, 60)
                if stop < 0: stop = 60
            if len(lines) == 0:
                continuation = "  "
            else:
                continuation = "%2i" % (len(lines)+1)
            lines.append( "%-80s" % ("TITLE   "+continuation+title[0:stop]) )
            title = title[stop:]
        return lines
    # End of titleLines

    def cryst1Lines(self, stru):
        """build lines corresponding to CRYST1 record"""
        lines = []
        latpar = ( stru.lattice.a, stru.lattice.b, stru.lattice.c,
                stru.lattice.alpha, stru.lattice.beta, stru.lattice.gamma )
        if latpar != (1.0, 1.0, 1.0, 90.0, 90.0, 90.0):
            line = "CRYST1%9.3f%9.3f%9.3f%7.2f%7.2f%7.2f" % latpar
            lines.append( "%-80s" % line )
        return lines
    # End of cryst1Lines

    def atomLines(self, stru, idx):
        """build ATOM records and possibly SIGATM, ANISOU or SIGUIJ records
        for structure stru atom number aidx
        """
        lines = []
        a = stru[idx]
        ad = a.__dict__
        rc = stru.cartesian(a)
        B = a.Biso()
        atomline = ( "ATOM  " +                         # 1-6
                     "%(serial)5i " +                   # 7-11, 12
                     "%(name)-4s" +                     # 13-16
                     "%(altLoc)c" +                     # 17
                     "%(resName)-3s " +                 # 18-20, 21
                     "%(chainID)c" +                    # 22
                     "%(resSeq)4i" +                    # 23-26
                     "%(iCode)c   " +                   # 27, 28-30
                     "%(x)8.3f%(y)8.3f%(z)8.3f" +       # 31-54
                     "%(occupancy)6.2f" +               # 55-60
                     "%(tempFactor)6.2f      " +        # 61-66, 67-72
                     "%(segID)-4s" +                    # 73-76
                     "%(element)2s" +                   # 77-78
                     "%(charge)-2s"                     # 79-80
                   ) % {
                  "serial" : idx+1,  "name" : a.element,  "altLoc" : " ",
                  "resName" : "",  "chainID" : " ",  "resSeq" : 1,
                  "iCode" : " ",  "x" : rc[0],  "y" : rc[1],  "z" : rc[2],
                  "occupancy" : a.occupancy,  "tempFactor" : B,  "segID" : "",
                  "element" : a.element,  "charge" : "" }
        lines.append(atomline)
        isotropic = num.all(a.U == a.U[0,0]*num.identity(3))
        if not isotropic:
            mid = " %7i%7i%7i%7i%7i%7i  " % tuple( num.around(1e4 *
                num.array([ a.U[0,0], a.U[1,1], a.U[2,2],
                    a.U[0,1], a.U[0,2], a.U[1,2] ])) )
            line = "ANISOU" + atomline[6:27] + mid + atomline[72:80]
            lines.append(line)
        # default values of standard deviations
        d_sigxyz = num.zeros(3, type=num.Float)
        d_sigo = 0.0
        d_sigU = num.zeros((3,3), type=num.Float)
        sigxyz = ad.get("sigxyz", d_sigxyz)
        sigo = ad.get("sigo", d_sigo)
        sigU = ad.get("sigU", d_sigU)
        sigB = 8*pi**2*num.average( [sigU[i,i] for i in range(3)] )
        sigmas = num.concatenate( (sigxyz, sigo, sigB) )
        # no need to print sigmas if they all round to zero
        hassigmas = num.any(num.abs(sigmas) >= num.array(3*[5e-4]+2*[5e-3])) \
                or num.any(num.abs(sigU) > 5.0e-5)
        if hassigmas:
            mid = "   %8.3f%8.3f%8.3f%6.2f%6.2f      " % tuple(sigmas)
            line = "SIGATM" + atomline[6:27] + mid + atomline[72:80]
            lines.append(line)
            # do we need SIGUIJ record?
            if not num.all(sigU == sigU[0,0]*num.identity(3)):
                mid = " %7i%7i%7i%7i%7i%7i  " % tuple( num.around(1e4 *
                    num.array([ sigU[0,0], sigU[1,1], sigU[2,2],
                        sigU[0,1], sigU[0,2], sigU[1,2] ])) )
                line = "SIGUIJ" + atomline[6:27] + mid + atomline[72:80]
                lines.append(line)
        return lines
    # End of atomLines

    def toLines(self, stru):
        """convert Structure stru to a list of lines in PDFFit format"""
        lines = []
        lines.extend( self.titleLines(stru) )
        lines.extend( self.cryst1Lines(stru) )
        for idx in range(len(stru)):
            lines.extend( self.atomLines(stru, idx) )
        line = (  "TER   " +            # 1-6
                  "%(serial)5i      " + # 7-11, 12-17
                  "%(resName)-3s " +    # 18-20, 21
                  "%(chainID)c" +       # 22
                  "%(resSeq)4i" +       # 23-26
                  "%(iCode)c" +         # 27
                  "%(blank)53s"         # 28-80
               ) % {
                  "serial" : len(stru)+1,  "resName" : "",  "chainID" : " ",
                  "resSeq" : 1, "iCode" : " ",  "blank" : " " }
        lines.append(line)
        lines.append("%-80s" % "END")
        return lines
    # End of toLines

# End of Parser
