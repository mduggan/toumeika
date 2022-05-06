import { module, test } from 'qunit';
import { setupTest } from 'toumeika/tests/helpers';

module('Unit | Model | group type', function (hooks) {
  setupTest(hooks);

  // Replace this with your real tests.
  test('it exists', function (assert) {
    let store = this.owner.lookup('service:store');
    let model = store.createRecord('group-type', {});
    assert.ok(model);
  });
});
