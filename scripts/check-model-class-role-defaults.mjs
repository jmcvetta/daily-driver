import assert from "node:assert/strict";
import { installModelClassDefaults, MODEL_CLASS_ROLE_DEFAULTS, MODEL_CLASS_ROLE_TAGS } from "../extensions/role-default-helper.mjs";

function settingsFixture(initialRoles = {}, initialTags = {}) {
  const roles = { ...initialRoles };
  const tags = { ...initialTags };
  const mutations = [];
  return {
    mutations,
    roles,
    tags,
    getModelRole(role) { return roles[role]; },
    overrideModelRoles(values) {
      Object.assign(roles, values);
      mutations.push(["roles", values]);
    },
    get(path) {
      assert.equal(path, "modelTags");
      return tags;
    },
    override(path, value) {
      assert.equal(path, "modelTags");
      Object.assign(tags, value);
      mutations.push(["tags", value]);
    },
  };
}

const clean = settingsFixture();
installModelClassDefaults(clean);
assert.deepEqual(clean.roles, MODEL_CLASS_ROLE_DEFAULTS);
assert.deepEqual(clean.tags, MODEL_CLASS_ROLE_TAGS);
assert.deepEqual(clean.mutations.map(([kind]) => kind), ["roles", "tags"]);

const operator = settingsFixture(
  { implementation: "operator/selected:high" },
  { implementation: { name: "Operator's implementation", color: "cyan" }, custom: { name: "Custom" } },
);
installModelClassDefaults(operator);
assert.equal(operator.roles.implementation, "operator/selected:high");
assert.equal(operator.roles.mechanical, MODEL_CLASS_ROLE_DEFAULTS.mechanical);
assert.deepEqual(operator.tags.implementation, { name: "Operator's implementation", color: "cyan" });
assert.deepEqual(operator.tags.mechanical, { name: "Mechanical" });
assert.deepEqual(operator.tags.custom, { name: "Custom" });

const cleared = settingsFixture({ implementation: "" });
installModelClassDefaults(cleared);
assert.equal(cleared.roles.implementation, MODEL_CLASS_ROLE_DEFAULTS.implementation);

console.log("check-model-class-role-defaults: runtime role defaults preserve existing role and tag metadata");

