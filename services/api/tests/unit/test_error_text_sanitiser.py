# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Every error string shown to the sysadmin goes through one sanitiser."""

from app.core.error_text import sanitize_error_text


def test_url_credentials_removed_even_with_slash_in_password():
    out = sanitize_error_text("connect postgresql://app:pa/ss/w0rd@db:5432/clew failed", 200)
    assert "pa/ss" not in out and "w0rd" not in out and "://***@db:5432/clew" in out


def test_sql_and_parameters_are_cut():
    text = "(psycopg.errors.X) boom\n[SQL: SELECT secret FROM t WHERE k=%(k)s]\n[parameters: {'k': 'tok'}]"
    out = sanitize_error_text(text, 300)
    assert out == "(psycopg.errors.X) boom" and "SELECT" not in out
    assert sanitize_error_text("bad [SQL: select 1]", 300) == "bad"


def test_first_line_only_and_length_cap_and_empty():
    assert sanitize_error_text("line one\nTraceback line two", 300) == "line one"
    assert len(sanitize_error_text("x" * 1000, 200)) == 200
    assert sanitize_error_text("", 200) == "" and sanitize_error_text(None, 200) == "None"
