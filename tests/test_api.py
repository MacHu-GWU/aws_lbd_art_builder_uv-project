# -*- coding: utf-8 -*-

from aws_lbd_art_builder_uv import api


def test():
    _ = api


if __name__ == "__main__":
    from aws_lbd_art_builder_uv.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_uv.api",
        preview=False,
    )
