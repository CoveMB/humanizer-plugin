.PHONY: test validate-humanizer-output eval-humanizer eval-humanizer-dry-run

test:
	python3 -m unittest discover -s tests -v

validate-humanizer-output:
	@test -n "$(OUTPUT_DIR)" || (echo "OUTPUT_DIR is required" >&2; exit 2)
	python3 scripts/validate_humanizer_outputs.py "$(OUTPUT_DIR)"

eval-humanizer:
	python3 scripts/run_humanizer_evals.py $(EVAL_ARGS)

eval-humanizer-dry-run:
	python3 scripts/run_humanizer_evals.py --dry-run $(EVAL_ARGS)
