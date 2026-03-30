import argparse
import json
import sys

from toolkit.drawthings import DrawThingsClient, DrawThingsConfig


def _normalize_models(raw_models):
    models = []
    for raw_model in raw_models or []:
        file_name = str(raw_model.get("file") or "").strip()
        if file_name == "":
            continue
        model_name = str(raw_model.get("name") or file_name).strip() or file_name
        models.append(
            {
                "file": file_name,
                "name": model_name,
                "version": raw_model.get("version"),
                "prefix": raw_model.get("prefix", ""),
            }
        )
    return sorted(models, key=lambda model: (str(model["name"]).lower(), str(model["file"]).lower()))


def main():
    parser = argparse.ArgumentParser(description="Probe a Draw Things server and return its catalog models.")
    parser.add_argument("--server", required=True, help="Draw Things server host or IP")
    parser.add_argument("--port", required=True, type=int, help="Draw Things server port")
    parser.add_argument("--use-tls", action="store_true", help="Attempt TLS first")
    parser.add_argument("--shared-secret", default="", help="Optional Draw Things shared secret")
    args = parser.parse_args()

    try:
        client = DrawThingsClient(
            DrawThingsConfig(
                server=args.server,
                port=args.port,
                use_tls=args.use_tls,
                shared_secret=args.shared_secret or None,
            )
        )
        catalog = client.get_catalog()
        payload = {
            "ok": True,
            "server": args.server,
            "port": args.port,
            "requested_use_tls": bool(args.use_tls),
            "resolved_use_tls": bool(client.resolved_use_tls if client.resolved_use_tls is not None else args.use_tls),
            "files": len(catalog.get("files", [])),
            "models": _normalize_models(catalog.get("models", [])),
        }
        print(json.dumps(payload))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
