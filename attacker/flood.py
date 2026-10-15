#!/usr/bin/env python3
"""Prueba HTTP controlada para el laboratorio de Fail2ban."""

from __future__ import annotations

import argparse
import os
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlparse

REQUEST_TIMEOUT_SECONDS = 2
REPORT_INTERVAL_SECONDS = 3
MAX_DURATION_SECONDS = 300
MAX_CONCURRENCY = 500
MAX_REQUESTS_PER_SECOND = 500


def setting(name: str, default: int, maximum: int) -> int:
    raw_value = os.environ.get(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as error:
        raise SystemExit(
            f"{name} debe ser un entero; se recibió {raw_value!r}"
        ) from error

    if not 1 <= value <= maximum:
        raise SystemExit(f"{name} debe estar entre 1 y {maximum}")
    return value


def validate_host(value: str) -> str:
    """Aceptar solo destinos HTTP/HTTPS con host explícito."""
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise argparse.ArgumentTypeError(
            "Indica una URL completa, por ejemplo http://localhost:8081"
        )
    if parsed.username or parsed.password:
        raise argparse.ArgumentTypeError("No incluyas credenciales en la URL")
    return value


def request_status(
    opener: urllib.request.OpenerDirector, target: str
) -> str:
    request = urllib.request.Request(target, method="GET")
    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return str(response.status)
    except urllib.error.HTTPError as error:
        return str(error.code)
    except (urllib.error.URLError, TimeoutError, OSError):
        return "000"


class RateLimiter:
    def __init__(self, requests_per_second: int) -> None:
        self.interval = 1 / requests_per_second
        self.next_request_at = 0.0
        self.lock = threading.Lock()

    def wait_for_turn(self, stop_event: threading.Event) -> bool:
        with self.lock:
            now = time.monotonic()
            scheduled_at = max(now, self.next_request_at)
            self.next_request_at = scheduled_at + self.interval
        return not stop_event.wait(max(0.0, scheduled_at - now))


def worker(
    target: str,
    deadline: float,
    stop_event: threading.Event,
    rate_limiter: RateLimiter,
    counts: Counter[str],
    counts_lock: threading.Lock,
) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while not stop_event.is_set() and time.monotonic() < deadline:
        if not rate_limiter.wait_for_turn(stop_event):
            break
        if time.monotonic() >= deadline:
            break

        code = request_status(opener, target)
        with counts_lock:
            counts[code] += 1


def snapshot(
    counts: Counter[str], counts_lock: threading.Lock
) -> Counter[str]:
    with counts_lock:
        return counts.copy()


def report(target: str, counts: Counter[str], final: bool = False) -> None:
    total = sum(counts.values())
    ok = counts["200"]
    limited = counts["429"]
    connection_errors = counts["000"]
    other_http = total - ok - limited - connection_errors

    label = (
        "RESULTADO"
        if final
        else f"[{datetime.now():%H:%M:%S}] solicitudes acumuladas"
    )

    print(
        f"  {label} para {target}:\n"
        f"    Total: {total}\n"
        f"    Exitosas (200): {ok}\n"
        f"    Limitadas (429): {limited}\n"
        f"    Otros códigos HTTP: {other_http}\n"
        f"    Errores de conexión/timeout (000): {connection_errors}",
        flush=True,
    )

    if final and total:
        print(
            f"  Porcentaje exitoso: {ok * 100 / total:.1f}%\n"
            f"  Porcentaje no exitoso: {(total - ok) * 100 / total:.1f}%",
            flush=True,
        )

        print("\n  Detalle por código:")
        for code, amount in sorted(counts.items()):
            print(f"    HTTP {code}: {amount}" if code != "000"
                  else f"    Error de conexión (000): {amount}")

def run_target(
    target: str, concurrency: int, duration: int, requests_per_second: int
) -> bool:
    print(
        f"\n--- Destino: {target} ({concurrency} workers, "
        f"máximo {requests_per_second} solicitudes/s, {duration}s) ---",
        flush=True,
    )
    counts: Counter[str] = Counter()
    counts_lock = threading.Lock()
    stop_event = threading.Event()
    rate_limiter = RateLimiter(requests_per_second)
    deadline = time.monotonic() + duration
    interrupted = False

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(
                worker,
                target,
                deadline,
                stop_event,
                rate_limiter,
                counts,
                counts_lock,
            )
            for _ in range(concurrency)
        ]
        try:
            while time.monotonic() < deadline:
                time.sleep(
                    min(REPORT_INTERVAL_SECONDS, deadline - time.monotonic())
                )
                report(target, snapshot(counts, counts_lock))
        except KeyboardInterrupt:
            interrupted = True
            stop_event.set()
            print("\nDeteniendo workers...", flush=True)
        finally:
            stop_event.set()

        for future in futures:
            future.result()

    report(target, snapshot(counts, counts_lock), final=True)
    return not interrupted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prueba HTTP controlada para un servicio del laboratorio."
    )
    parser.add_argument(
        "host",
        type=validate_host,
        help="URL del servicio autorizado, por ejemplo http://localhost:8081",
    )
    args = parser.parse_args()

    duration = setting("DURATION", 20, MAX_DURATION_SECONDS)
    concurrency = setting("CONCURRENCY", 40, MAX_CONCURRENCY)
    requests_per_second = setting("REQUESTS_PER_SECOND", 50, MAX_REQUESTS_PER_SECOND)

    print(
        "=== Prueba HTTP de laboratorio ===\n"
        f"Destino: {args.host}\n"
        f"Workers: {concurrency}; máximo solicitudes/s: "
        f"{requests_per_second}; duración: {duration}s",
        flush=True,
    )

    run_target(args.host, concurrency, duration, requests_per_second)
    print("\n=== Prueba terminada ===")
    print("Los errores pueden indicar bloqueo, error HTTP o tiempo de espera.")


if __name__ == "__main__":
    main()
