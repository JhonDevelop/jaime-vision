from jaime.spatial.core import SpatialCore, SpatialObject, Vec3
from jaime.spatial.gestures import HandSample, PinchMachine
from jaime.spatial.learner import GestureLibrary
from jaime.spatial.policy import ProposedAction, evaluate
from jaime.spatial.inference import LocalInference
from jaime.spatial.geometry import CameraObservation, DisplayPlane, synchronized
from jaime.spatial.scene import SceneGraph
from jaime.spatial.benchmark import Metrics, assess
import unittest

class SpatialTests(unittest.TestCase):
    def test_pinch_hysteresis_and_reference(self):
        c = SpatialCore(); c.add(SpatialObject("folder", "folder", Vec3(0,0,0)))
        m = PinchMachine(c)
        def s(t, gap):
            return HandSample("joao", Vec3(0,0,0), Vec3(gap,0,0), 1.0, t, .99, "folder")
        self.assertEqual(m.update(s(0, .2)), [])
        self.assertEqual([e.kind for e in m.update(s(.1, .2))], ["spatial.select", "gesture.grab"])
        self.assertEqual(c.resolve("joao", "isso").id, "folder")
        self.assertEqual(m.update(s(.2, .35))[0].kind, "gesture.drag")
        self.assertEqual(m.update(s(.3, .5))[0].kind, "gesture.release")

    def test_personal_gesture_rejects_negative(self):
        lib=GestureLibrary()
        positive=[[(0.,0.),(.5,.5),(1.,1.)]]*3
        lib.teach("arquivar", positive)
        name, conf=lib.recognize([(10.,10.),(11.,11.),(12.,12.)], {"arquivar"})
        self.assertEqual(name, "arquivar")
        self.assertGreater(conf, .8)
        lib.teach("arquivar", positive, negative=True)
        self.assertIsNone(lib.recognize(positive[0])[0])

    def test_sensitive_action_never_direct(self):
        a=ProposedAction("move_to_trash", "bub", "joao", .99)
        self.assertEqual(evaluate(a, unlocked=True, owner=True).status, "review")
        self.assertEqual(evaluate(ProposedAction("open", "bub", "guest", .99), unlocked=True, owner=False).status, "deny")

    def test_local_endpoint_only(self):
        with self.assertRaises(ValueError):
            LocalInference("https://api.vendor.com/v1", "model")
        self.assertEqual(LocalInference("http://127.0.0.1:11434/v1", "model").model, "model")

    def test_display_mapping_and_stale_multicamera(self):
        plane=DisplayPlane("center",Vec3(0,0,0),Vec3(1,0,0),Vec3(0,1,0),(2560,0,2560,1440))
        self.assertEqual(plane.pixel_from_room(Vec3(.5,.5,.01)),(3840,720))
        self.assertIsNone(plane.pixel_from_room(Vec3(.5,.5,.3)))
        a=CameraObservation("a",1.0,10,(20,20),.9)
        b=CameraObservation("b",1.01,17,(24,21),.9)
        self.assertTrue(synchronized([a,b]))
        self.assertFalse(synchronized([a,CameraObservation("b",1.1,18,(24,21),.9)]))

    def test_scene_and_evolution_gate(self):
        c=SpatialCore()
        c.add(SpatialObject("api","backend",Vec3(0,0,0)))
        c.add(SpatialObject("db","database",Vec3(1,0,0)))
        g=SceneGraph(c); g.link("api","db","uses","voice:joao")
        self.assertEqual(g.snapshot()["edges"][0]["target"],"db")
        baseline=Metrics(.96,.3,30,100)
        self.assertFalse(assess(baseline,Metrics(.97,.4,25,100))[0])
        self.assertTrue(assess(baseline,Metrics(.97,.2,29,100))[0])
