"""
ui/rate_limiter.py — Sliding window rate limiter for the Berlin Zoning Assistant.

Uses st.session_state to store per-session request timestamps.
Controlled by RATE_LIMITING_ENABLED in config.py — set to False to disable
during development or testing without changing any other code.
"""

import time
import streamlit as st
from config import (
	RATE_LIMITING_ENABLED,
	RATE_LIMIT_REQUESTS,
	RATE_LIMIT_WINDOW_SECONDS,
)


def check_rate_limit() -> tuple[bool, int]:
	"""
	Check whether the current request is within the allowed rate.
	Uses a sliding window: only requests within the last
	RATE_LIMIT_WINDOW_SECONDS seconds count against the limit.
	Returns:	(True, 0)  — request is allowed
				(False, wait_seconds)  — limit exceeded; caller should show a message
		                         		telling the user to wait `wait_seconds` seconds
	"""
	if not RATE_LIMITING_ENABLED:
		return True, 0

	now = time.time()

	# Initialise timestamp list in session state on first call
	if "request_timestamps" not in st.session_state:
		st.session_state.request_timestamps = []

	# Drop timestamps that have fallen outside the sliding window
	st.session_state.request_timestamps = [
		t for t in st.session_state.request_timestamps
		if now - t < RATE_LIMIT_WINDOW_SECONDS
	]

	if len(st.session_state.request_timestamps) >= RATE_LIMIT_REQUESTS:
		# Tell the user how long until the oldest request falls out of the window
		oldest = st.session_state.request_timestamps[0]
		wait_seconds = int(RATE_LIMIT_WINDOW_SECONDS - (now - oldest)) + 1
		return False, wait_seconds

	# Request is within limit — record it and allow
	st.session_state.request_timestamps.append(now)
	return True, 0