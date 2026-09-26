import assert from "node:assert/strict";
import { installModelClassDefaults, MODEL_CLASS_ROLE_DEFAULTS, MODEL_CLASS_ROLE_TAGS } from "../extensions/role-default-helper.mjs";

function settingsFixture(initialRoles = {}, initialTags = {}) {
  const roles = { ...initialRoles };
  const tags = { ...initialTags };
  const mutations = [];
  const settings = {
    mutations,
    roles,
    tags,
    getModelRole(role) { return roles[role]; },
    overrideModelRoles(values) {
      Object.assign(roles, values);
      mutations.push(["roles", values]);
    },
  };
  const modelTagsSetting = {
    get(scope) {
      assert.equal(scope, settings);
      return tags;
    },
    override(scope, value) {
      assert.equal(scope, settings);
      Object.assign(tags, value);
      mutations.push(["tags", value]);
    },
  };
  return { settings, modelTagsSetting, roles, tags, mutations };
}

const clean = settingsFixture();
assert.equal(clean.settings.get, undefined, "Omp Settings does not expose generic get");
installModelClassDefaults(clean.settings, clean.modelTagsSetting);
assert.deepEqual(clean.roles, MODEL_CLASS_ROLE_DEFAULTS);
assert.deepEqual(clean.tags, MODEL_CLASS_ROLE_TAGS);
assert.deepEqual(clean.mutations.map(([kind]) => kind), ["roles", "tags"]);

const operator = settingsFixture(
  { implementation: "operator/selected:high" },
  { implementation: { name: "Operator's implementation", color: "cyan" }, custom: { name: "Custom" } },
);
installModelClassDefaults(operator.settings, operator.modelTagsSetting);
assert.equal(operator.roles.implementation, "operator/selected:high");
assert.equal(operator.roles.mechanical, MODEL_CLASS_ROLE_DEFAULTS.mechanical);
assert.deepEqual(operator.tags.implementation, { name: "Operator's implementation", color: "cyan" });
assert.deepEqual(operator.tags.mechanical, { name: "Mechanical" });
assert.deepEqual(operator.tags.custom, { name: "Custom" });

const cleared = settingsFixture({ implementation: "" });
installModelClassDefaults(cleared.settings, cleared.modelTagsSetting);
assert.equal(cleared.roles.implementation, MODEL_CLASS_ROLE_DEFAULTS.implementation);

console.log("check-model-class-role-defaults: typed model-tag handles preserve runtime role and tag metadata");

