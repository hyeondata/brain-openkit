"""Optional local runtime for the pinned Korean decision checkpoint.

Importing this module never loads inference libraries or downloads weights.
"""

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
from ipaddress import ip_address
import json
import math
import socket

from .providers import MAX_REQUEST_BYTES, _reject_constant, _text, _unique_object


MODEL_ID = "mmetamong/ko-decision-roberta-large"
MODEL_REVISION = "dfd606fff30d52963c0073659ff9a8f6bf1fce6d"
MAX_PAIR_TOKENS = 512


class DecisionRequestError(ValueError):
    """An HTTP status and safe code, without any request text."""

    def __init__(self, status, code):
        self.status = status
        self.code = code
        super().__init__(code)


def _validate_request(payload):
    if not isinstance(payload, dict) or set(payload) != {"model", "state", "questions"}:
        raise DecisionRequestError(400, "invalid_request")
    if payload["model"] != MODEL_ID:
        raise DecisionRequestError(400, "invalid_model")
    questions = payload["questions"]
    if not _text(payload["state"]) or not isinstance(questions, dict) or set(questions) != {"decision"}:
        raise DecisionRequestError(400, "invalid_request")
    question = questions["decision"]
    if not isinstance(question, dict) or set(question) != {"type", "instructions", "criteria"}:
        raise DecisionRequestError(400, "invalid_question")
    criteria = question["criteria"]
    if (question["type"] != "choice" or not _text(question["instructions"])
            or not isinstance(criteria, dict) or not 1 <= len(criteria) <= 10):
        raise DecisionRequestError(400, "invalid_question")
    if any(not _text(key) or not _text(value)
           or any(ord(char) < 32 or ord(char) == 127 for char in key)
           for key, value in criteria.items()):
        raise DecisionRequestError(400, "invalid_choices")
    # JSON permits escaped lone surrogates, but tokenizers need valid Unicode.
    try:
        for text in (payload["state"], question["instructions"], *criteria, *criteria.values()):
            text.encode("utf-8")
    except UnicodeError:
        raise DecisionRequestError(400, "invalid_request") from None
    return payload["state"], question["instructions"], criteria


class DecisionEngine:
    """Prepare complete pairs and normalize one question's option scores.

    ``score_batch`` performs inference on an unpadded token batch. Keeping it
    separate lets the transport and input limits work without importing torch.
    Probabilities and top-versus-uniform confidence are not calibrated accuracy.
    """

    def __init__(self, tokenizer, score_batch, batch_size=4):
        if type(batch_size) is not int or not 1 <= batch_size <= 10:
            raise ValueError("invalid_batch_size")
        self.tokenizer = tokenizer
        self.score_batch = score_batch
        self.batch_size = batch_size

    def decide(self, payload):
        state, instruction, criteria = _validate_request(payload)
        texts = [f"{instruction} {option}" for option in criteria.values()]
        encoded = self.tokenizer(texts, [state] * len(texts), padding=False,
                                 truncation=False, return_token_type_ids=False)
        lengths = [len(row) for row in encoded["input_ids"]]
        if max(lengths) > MAX_PAIR_TOKENS:
            raise DecisionRequestError(413, "input_too_long")
        scores = []
        for start in range(0, len(texts), self.batch_size):
            batch = {key: value[start:start + self.batch_size] for key, value in encoded.items()}
            values = self.score_batch(batch)
            if len(values) != len(batch["input_ids"]) or any(
                    type(score) not in (int, float) or not math.isfinite(score) for score in values):
                raise RuntimeError("invalid_model_output")
            scores.extend(values)
        largest = max(scores)
        weights = [math.exp(score - largest) for score in scores]
        total = sum(weights)
        probabilities = {key: weight / total for key, weight in zip(criteria, weights)}
        choice = max(probabilities, key=probabilities.get)
        count = len(criteria)
        confidence = ((probabilities[choice] - 1 / count) / (1 - 1 / count)
                      if count > 1 else 1.0)
        return {
            "model": MODEL_ID, "model_revision": MODEL_REVISION,
            "answers": {"decision": {
                "type": "choice", "choice": choice, "probabilities": probabilities,
                "confidence": max(0.0, min(1.0, confidence)),
            }},
            "usage": {
                "input_tokens": sum(lengths), "output_tokens": 0,
                "state_tokens": len(self.tokenizer.encode(state, add_special_tokens=False)),
                "state_tokens_dropped": 0, "truncated": False, "truncated_questions": [],
                "max_pair_tokens": max(lengths), "model_revision": MODEL_REVISION,
            },
        }


def _loopback_host(host):
    if host == "localhost":
        return "127.0.0.1"
    try:
        if ip_address(host).is_loopback:
            return host
    except ValueError:
        pass
    raise ValueError("host must be a loopback IP address or localhost")


def create_server(engine, host="127.0.0.1", port=8010):
    """Serve serial local inference with bounded bodies and no request logs."""
    host = _loopback_host(host)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass

        def reply(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass

        def error(self, status, code):
            self.reply(status, {"error": {"code": code}})

        def send_error(self, code, message=None, explain=None):
            self.error(code, "invalid_http_request")

        def do_GET(self):
            if self.path != "/v1/models":
                return self.error(404, "not_found")
            self.reply(200, {"models": [{
                "name": MODEL_ID, "description": "Korean typed decisions; uncalibrated option probabilities",
                "release_date": "2026-10-05", "revision": MODEL_REVISION,
                "max_length": MAX_PAIR_TOKENS, "truncate_states": False, "license": "cc-by-sa-4.0",
            }]})

        def do_POST(self):
            if self.path != "/v1/systemone":
                return self.error(404, "not_found")
            # No CORS or browser-origin requests: this server receives local CLI traffic.
            if "Origin" in self.headers:
                return self.error(403, "browser_request_forbidden")
            if self.headers.get_content_type() != "application/json":
                return self.error(415, "expected_json")
            lengths = self.headers.get_all("Content-Length", [])
            if ("Transfer-Encoding" in self.headers or len(lengths) != 1
                    or not 1 <= len(lengths[0]) <= 10
                    or not lengths[0].isascii() or not lengths[0].isdigit()):
                return self.error(400, "invalid_content_length")
            length = int(lengths[0])
            if length > MAX_REQUEST_BYTES:
                return self.error(413, "request_too_large")
            try:
                body = self.rfile.read(length)
                if len(body) != length:
                    return self.error(400, "incomplete_request")
                payload = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object,
                                     parse_constant=_reject_constant)
            except (ValueError, UnicodeError, RecursionError):
                return self.error(400, "invalid_json")
            except (OSError, TimeoutError):
                return self.error(408, "request_timeout")
            try:
                response = engine.decide(payload)
            except DecisionRequestError as error:
                return self.error(error.status, error.code)
            except Exception:
                return self.error(500, "inference_failed")
            self.reply(200, response)

    class LocalServer(HTTPServer):
        address_family = socket.AF_INET6 if ":" in host else socket.AF_INET

        def handle_error(self, request, client_address):
            # socketserver's default traceback can contain request information.
            pass

    return LocalServer((host, port), Handler)


def load_engine(device="auto", batch_size=4, threads=4, cache_dir=None, local_files_only=False):
    """Load only the pinned checkpoint and safetensors, after explicit startup."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.set_num_threads(threads)
    if device == "auto":
        device = ("cuda" if torch.cuda.is_available() else
                  "mps" if torch.backends.mps.is_available() else "cpu")
    common = {"revision": MODEL_REVISION, "cache_dir": cache_dir,
              "local_files_only": local_files_only, "trust_remote_code": False}
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, **common)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_ID, use_safetensors=True, **common,
    ).to(device).eval()
    if model.config.model_type != "roberta" or model.config.num_labels != 1:
        raise ValueError("invalid_model_configuration")

    def score_batch(batch):
        tensors = tokenizer.pad(batch, padding=True, return_tensors="pt").to(device)
        with torch.inference_mode():
            logits = model(**tensors).logits
        if logits.ndim != 2 or logits.shape[1] != 1:
            raise RuntimeError("invalid_model_output")
        return logits[:, 0].detach().cpu().tolist()

    return DecisionEngine(tokenizer, score_batch, batch_size=batch_size)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1", help="Loopback bind address")
    parser.add_argument("--port", type=int, default=8010, help="Server port")
    parser.add_argument("--device", choices=("auto", "cpu", "mps", "cuda"), default="auto")
    parser.add_argument("--batch-size", type=int, default=4, help="Options per model batch (1–10)")
    parser.add_argument("--threads", type=int, default=4, help="PyTorch CPU threads (1–64)")
    parser.add_argument("--cache-dir", help="Hugging Face model cache directory")
    parser.add_argument("--local-files-only", action="store_true", help="Load only cached model files")
    args = parser.parse_args(argv)
    try:
        host = _loopback_host(args.host)
    except ValueError as error:
        parser.error(str(error))
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if not 1 <= args.batch_size <= 10 or not 1 <= args.threads <= 64:
        parser.error("batch-size must be 1–10 and threads must be 1–64")
    try:
        engine = load_engine(args.device, args.batch_size, args.threads, args.cache_dir, args.local_files_only)
    except ImportError:
        parser.error("Install the optional ko-decision runtime: pip install '.[ko-decision]' from the source checkout")
    except Exception:
        parser.error("Could not load the pinned ko-decision checkpoint; check device, cache, and network access")
    try:
        with create_server(engine, host, args.port) as server:
            print(f"ko-decision ready on {host}:{args.port} ({MODEL_ID}@{MODEL_REVISION})", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return 130
    except OSError:
        parser.error("Could not start the local server; check the loopback address and port")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
