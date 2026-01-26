from collections.abc import Iterable
import dataclasses
from queue import Queue
import sys
from typing import Any
from types import TracebackType



def only_nonnone(input: dict | Iterable[tuple[Any, Any]]) -> dict:
    return {k: v for (k, v) in dict(input) if v is not None}


def dataclass_nonnones_dict(input) -> dict:
    return only_nonnone(dataclasses.asdict(input))


def hex_string_to_bytes(hex_str: str) -> bytes:
    return bytes(
        int(hex_str[i:i+2], base=16) for i in range(len(hex_str) // 2)
        )


def autoint(x: str) -> int:
    return int(x, base=0)


def hexint(x: str) -> int:
    return int(x, base=16)


def bytes_to_hex_string(bytes_: bytes, delimiter: str = "") -> str:
    return delimiter.join(f"{x:02X}" for x in bytes_)



class _SynchronizedMethodCall:
    def __init__(self, method_name: str, *args, **kwargs):
        self._result = Queue()
        self.method_name = method_name
        self.call_args = args
        self.call_kwargs = kwargs

    def put_result(
            self,
            error: tuple[BaseException, TracebackType] | None = None,
            return_val: Any = None
            ):
        self._result.put((error, return_val))

    def get_result(self):
        if self._result is None:
            raise RuntimeError("get_result() called more than once?")
        error, return_val = self._result.get()
        self._result = None
        if error is not None:
            exc_val, traceback = error
            raise exc_val.with_traceback(traceback)
        return result


class SynchronizedAccess:
    InnerClass: type
    only_methods = ()
    exclude_methods = ()

    def __init__(self):
        self._method_names = None
        self.worker = xxxxxxxxxxxxxx
        # TODO FIXME
        init_error_out = Queue()
        self._method_calls_in = Queue()
        # TODO figure out how to pass it the queues, init args, etc
        self.worker.start()
        init_error = init_error_out.get()
        if init_error is not None:
            exc_val, traceback = init_error
            raise exc_val.with_traceback(traceback)

    def _get_method_names(self):
        if self._method_names is None:
            self._method_names = self._method_names_out.get()
            self._method_names_out = None
        return self._method_names


    @classmethod
    def _worker_main(cls, XXXXXXXX):
        try:
            wrapped_inst = cls.InnerClass(*init_args, **init_kwargs)
        except Exception as e:
            exc_type, exc_val, tb = sys.exc_info()
            init_error_out.put((exc_val, tb))
            return
        init_error_out.put(None)
        # FIXME TODO build list of eligible methods and send back method names
        method_names_out = None
        while True:
            if self._quit_flag.is_set():
                break
            call = calls_in.get()
            if call is None:
                continue
            try:
                return_val = getattr(wrapped_inst, call.method_name
                    )(*call.call_args, **call.call_kwargs)
            except Exception as e:
                exc_type, exc_val, tb = sys.exc_info()
                call.put_result(error=(exc_val, tb))
            call.put_result(return_val=return_val)
            call = None

    def _synchronized_call(self, method_name: str | None, *args, **kwargs
                           ) -> Any:
        if method_name is None:
            self._method_calls_in.put(None)
            return
        call = _SynchronizedMethodCall(method_name, *args, **kwargs)
        self._method_calls_in.put(call)
        return call.get_result()

    def close(self):
        if self.worker is not None:
            self._synchronized_call_if_has_method("close")
            self._quit_flag.set()
            self._synchronized_call(None)
            self.worker.join()
        self.worker = None
