import Adapter from '@ember-data/adapter';

export default class ApplicationAdapter extends Adapter {
  findRecord(store, type, id) {
    return (async (resolve, reject) => {
      var db = await window.appdb();
      return db.exec("SELECT * FROM '" + type.modelName + "' where id=?;", [id])[0];
    })();
  }

  findAll(store, type) {
    return (async (resolve, reject) => {
      var db = await window.appdb();
      return db.exec("SELECT * FROM '" + type.modelName + "';")[0];
    })();
  }

  queryRecord(store, type, query) {}

  query(store, type, query) {}

  createRecord() {
    return false;
  }

  updateRecord() {
    return false;
  }

  deleteRecord() {
    return false;
  }
}
