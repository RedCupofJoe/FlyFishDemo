.PHONY: test test-ui smoke manifests kustomize

export PYTHONPATH := components/flyfish-common/src:components/mcp/src:components/agents/src:components/indexer/src

test:
	python3 -m pytest tests -q

test-ui:
	cd components/ui && npm test

smoke:
	python3 scripts/smoke-local.py

manifests:
	python3 scripts/render_manifests.py

kustomize:
	kubectl kustomize deploy/ai >/tmp/flyfish-ai.yaml
	kubectl kustomize deploy/ui >/tmp/flyfish-ui.yaml
	@echo "kustomize ok ai=$$(grep -c '^kind:' /tmp/flyfish-ai.yaml) ui=$$(grep -c '^kind:' /tmp/flyfish-ui.yaml)"
