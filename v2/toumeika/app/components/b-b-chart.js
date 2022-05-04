import Component from '@glimmer/component';
import { action } from "@ember/object";
//import { did-render } from "@ember/render-modifiers";

function makeChart() {
    // generate the chart
    let elem = document.getElementById("chart");
    console.log("addint chart to " + elem);
    var chart = bb.generate({
        bindto: elem,
        data: {
          // for ESM import usage, import 'line' module and execute it as
          // type: line(),
          type: "line",
          columns: [
              ["datas", 30, 200, 100, 400, 150, 250]
          ]
        }
    });
}

function waitForChart() {
    console.log("waitForChart");
    if (document.getElementById("chart") == null) {
        setTimeout(waitForChart, 100);
        return;
    }
    makeChart();
}


 export default class BBChart extends Component {
    constructor(owner, args) {
        console.log("constructor");
        super(owner, args);
        this.madeChart = false;
    }

    get addChart() {
        console.log("addchart");
        waitForChart();
   }
}

