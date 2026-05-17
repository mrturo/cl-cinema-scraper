"""APScheduler vendor stub — raises informative error when used."""


class AsyncIOScheduler:
    def __init__(self, **kwargs: object) -> None:
        self._kwargs = kwargs

    def add_job(self, *args: object, **kwargs: object) -> None:
        pass

    def start(self) -> None:
        raise RuntimeError(
            "APScheduler is not installed. "
            "The scheduler cannot run in the current environment."
        )

    def shutdown(self, wait: bool = True) -> None:
        pass
