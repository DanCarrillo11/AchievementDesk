"""SteamAchievementManager: English-language Windows desktop application."""
import argparse


def main():
    from workspace import APP_NAME, VERSION
    parser = argparse.ArgumentParser(description=f"{APP_NAME} {VERSION}")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    parser.add_argument("--worker", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--demo", action="store_true", help="Use synthetic data without connecting to Steam")
    parser.add_argument("--library", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--refresh-library", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--render-demo", help=argparse.SUPPRESS)
    parser.add_argument("--render-public-demo", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.render_demo:
        from render_demo import render
        render(args.render_demo)
    elif args.render_public_demo:
        from public_preview import render
        render(args.render_public_demo)
    elif args.library:
        from worker import run_library
        run_library(refresh=args.refresh_library)
    elif args.worker is not None:
        from worker import run
        run(args.worker, args.demo)
    else:
        from modern_ui import launch
        launch(args.demo)


if __name__ == "__main__":
    main()
