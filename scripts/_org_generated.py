HAND_EDITS_ARE_DRIFT = True
GENERATED_BY = "scripts/gen_org.py"
GENERATED_FROM = "org/schema.daslab.yaml"
REGENERATE_COMMAND = "python3 scripts/gen_org.py"
DRIFT_GATE = "scripts/check_org_drift.py"

NEVER_AUTO_APPROVE = ('new_goal', 'security_sensitive', 'schema_migration', 'gate5_deployment', 'governance_or_policy', 'permission_change', 'secret_change')
GATES = ('GATE-1', 'GATE-2', 'GATE-3', 'GATE-4', 'GATE-5', 'GATE-6')
ROLES = ('backend-em', 'coo', 'cpo', 'cto', 'founder', 'qa-lead', 'security-lead', 'sre-lead')
GATE_OWNERS = {'GATE-1': ('cpo', 'founder'), 'GATE-2': ('cto', 'security-lead'), 'GATE-3': ('backend-em', 'cto'), 'GATE-4': ('qa-lead', 'security-lead'), 'GATE-5': ('coo', 'sre-lead'), 'GATE-6': ('cto',)}
