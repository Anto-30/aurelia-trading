"""Read-only advisory adapters for supervised AURELIA model workers.

Each adapter consumes one JSON task request from stdin and emits one JSON
response. Adapters do not receive broker credentials or capital authority.
"""
