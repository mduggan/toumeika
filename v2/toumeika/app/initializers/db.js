import initSqlJs from 'sql.js';

export function initialize(application) {
  const sqlconf = { locateFile: (filename) => `${filename}` };
  async function resolveDb() {
    return (async (resolve, reject) => {
      var SQL = await initSqlJs(sqlconf);
      //Create the database
      var buf = await fetch('/shikin.db').then((res) => res.arrayBuffer());
      return new SQL.Database(new Uint8Array(buf));
    })();
  }
  window.appdb = resolveDb;
}

export default {
  initialize,
};
