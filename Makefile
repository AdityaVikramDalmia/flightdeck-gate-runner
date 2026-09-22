.PHONY: test check
check:
	python3 -m py_compile gate_runner/cli.py tests/test_gate.py
	bash -n bin/gate-run

test: check
	python3 -m unittest discover -s tests -v
