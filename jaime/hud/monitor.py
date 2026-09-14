"""Monitoramento da máquina para o HUD (psutil). Emite um evento `sistema` a cada 2 s."""
from __future__ import annotations
import asyncio, time
from .events import bus

async def loop_monitor(intervalo: float = 2.0):
    try:
        import psutil
    except ImportError:
        bus.emitir("sistema", erro="psutil não instalado"); return
    psutil.cpu_percent(None)
    n0, t0 = psutil.net_io_counters(), time.time()
    while True:
        await asyncio.sleep(intervalo)
        n1, t1 = psutil.net_io_counters(), time.time()
        dt = max(t1 - t0, 1e-3)
        dados = {
            "cpu": psutil.cpu_percent(None), "ram": psutil.virtual_memory().percent,
            "disco": psutil.disk_usage("/").percent,
            "up_kbs": round((n1.bytes_sent - n0.bytes_sent) / dt / 1024, 1),
            "down_kbs": round((n1.bytes_recv - n0.bytes_recv) / dt / 1024, 1),
            "procs": len(psutil.pids()), "uptime_h": round((time.time() - psutil.boot_time()) / 3600, 1),
        }
        bat = getattr(psutil, "sensors_battery", lambda: None)()
        if bat: dados["bateria"] = bat.percent
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                dados["temp"] = round(max(e.current for v in temps.values() for e in v if e.current), 1)
        except Exception:
            pass
        n0, t0 = n1, t1
        bus.emitir("sistema", **dados)
