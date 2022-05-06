import { run, scheduleOnce } from '@ember/runloop';
import Route from '@ember/routing/route';
import { service } from '@ember/service';
import _ from 'lodash/lodash';

export default class IndexRoute extends Route {
  @service store;

  model() {
    var alldocs = this.store.findAll('document');
    return (async (resolve, reject) => {
        var docs = await alldocs;
        var newdocs = _.filter(docs.toArray(), (x) => { return x.year > 2008; });
        var byyear = _.countBy(newdocs, (x) => { return x.year; });
        var cols = [_.concat(['Year'], _.keys(byyear)), _.concat(['Documents'], _.toArray(byyear))];
        var model = {x: 'Year', columns: cols};
        return model;
    })();
  }
}
