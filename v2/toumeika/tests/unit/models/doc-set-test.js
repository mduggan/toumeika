import { module, test } from 'qunit';
import { setupTest } from 'toumeika/tests/helpers';

module('Unit | Model | doc set', function (hooks) {
  setupTest(hooks);

  // Replace this with your real tests.
  test('it exists', function (assert) {
    let store = this.owner.lookup('service:store');
    let model = store.createRecord('doc-set', {});
    assert.ok(model);
  });
});
