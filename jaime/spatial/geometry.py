"""Transformações básicas e sincronização; triangulação fica para calibração OpenCV."""
from __future__ import annotations
from dataclasses import dataclass
from .core import Vec3

@dataclass(frozen=True)
class CameraObservation:
    camera_id: str
    timestamp: float
    frame_id: int
    point_px: tuple[float, float]
    confidence: float

def synchronized(observations: list[CameraObservation], tolerance_s: float = .025) -> bool:
    return (len(observations) >= 2 and
            len({o.camera_id for o in observations}) == len(observations) and
            max(o.timestamp for o in observations) - min(o.timestamp for o in observations) <= tolerance_s and
            all(o.confidence >= .65 for o in observations))

@dataclass(frozen=True)
class DisplayPlane:
    id: str
    origin: Vec3
    right: Vec3
    down: Vec3
    logical_bounds: tuple[int, int, int, int]

    def pixel_from_room(self, p: Vec3, max_plane_error_m: float = .08) -> tuple[int,int] | None:
        # right/down are basis vectors spanning the calibrated physical display in meters.
        u = Vec3(p.x-self.origin.x, p.y-self.origin.y, p.z-self.origin.z)
        rr = self.right.x**2+self.right.y**2+self.right.z**2
        dd = self.down.x**2+self.down.y**2+self.down.z**2
        cross = self.right.x*self.down.x+self.right.y*self.down.y+self.right.z*self.down.z
        det = rr*dd-cross*cross
        if det < 1e-10:
            raise ValueError("degenerate display calibration")
        ur = u.x*self.right.x+u.y*self.right.y+u.z*self.right.z
        ud = u.x*self.down.x+u.y*self.down.y+u.z*self.down.z
        a=(ur*dd-ud*cross)/det; b=(ud*rr-ur*cross)/det
        residual=Vec3(u.x-a*self.right.x-b*self.down.x,
                      u.y-a*self.right.y-b*self.down.y,
                      u.z-a*self.right.z-b*self.down.z)
        if not (0 <= a <= 1 and 0 <= b <= 1) or residual.distance(Vec3(0,0,0)) > max_plane_error_m:
            return None
        x,y,w,h=self.logical_bounds
        return (round(x+a*w), round(y+b*h))
