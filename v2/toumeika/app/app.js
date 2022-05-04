import Application from '@ember/application';
import Resolver from 'ember-resolver';
import loadInitializers from 'ember-load-initializers';
import config from 'toumeika/config/environment';
import initSqlJs from "sql.js";

export default class App extends Application {
  modulePrefix = config.modulePrefix;
  podModulePrefix = config.podModulePrefix;
  Resolver = Resolver;
}

let sqlconf = {
      locateFile: filename => `${filename}`
}
// The `initSqlJs` function is globally provided by all of the main dist files if loaded in the browser.
// We must specify this locateFile function if we are loading a wasm file from anywhere other than the current html page's folder.
initSqlJs(sqlconf).then(function(SQL) {
  //Create the database
  const dataPromise = fetch("/shikin.db").then(res => res.arrayBuffer());
  dataPromise.then(function(buf) {
    const db = new SQL.Database(new Uint8Array(buf));
    // Prepare a statement
    const result = db.exec("SELECT count(*) FROM 'group';");

    console.log('Group count: ' + JSON.stringify(result[0].values[0][0]));
  });
});

loadInitializers(App, config.modulePrefix);
