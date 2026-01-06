import sys

from fastapi.routing import APIRoute


def _paths(routes):
    return [r.path for r in routes if isinstance(r, APIRoute)]


def main() -> None:
    import app
    import app.api.routes as routes
    import app.main as main_module

    print("sys.path:")
    for entry in sys.path:
        print(entry)

    print("\napp.__file__:", getattr(app, "__file__", "missing"))
    print("routes.__file__:", getattr(routes, "__file__", "missing"))
    print("main.__file__:", getattr(main_module, "__file__", "missing"))

    print("\nrouter paths:", _paths(routes.router.routes))
    print("share_router paths:", _paths(routes.share_router.routes))
    print("media_router paths:", _paths(routes.media_router.routes))

    print("\napp.routes:", _paths(main_module.app.routes))


if __name__ == "__main__":
    main()
