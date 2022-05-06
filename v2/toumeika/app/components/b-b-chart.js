import Component from '@glimmer/component';
import { action } from '@ember/object';
import { tracked } from '@glimmer/tracking';

export default class BBChart extends Component {
  @tracked columns = [];

  constructor(owner, args) {
    super(owner, args);
  }

  makeChart(elem) {
    this.chart = bb.generate({
      bindto: elem,
      data: {
        type: 'line',
        x: this.args.x,
        columns: this.args.columns || [],
      },
      axis: {
        y: {
          min: 0,
          padding: { bottom: 0 }
        }
      },
    });
  }

  waitForChart(elemname) {
    var elem = document.getElementById('chart');
    if (elem == null) {
      setTimeout(waitForChart, 100);
      return;
    }
    this.makeChart(elem);
  }

  get addChart() {
    this.waitForChart();
  }
}
