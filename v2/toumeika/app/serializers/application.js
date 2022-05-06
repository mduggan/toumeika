import EmberObject from '@ember/object';
import _ from 'lodash/lodash';

export default class SqliteSerializer extends EmberObject {
  normalizeResponse(store, schema, rawPayload, id, requestType) {
      if (!rawPayload.columns || !rawPayload.values)
          return { data: [], meta: {} };

      if (requestType === "findAll") {
          var data = _.map(rawPayload.values, (val) => {
            var datum = { 'type': schema.modelName };
            datum['attributes'] = _.zipObject(rawPayload.columns, val);
            datum['id'] = datum['attributes']['id'];
            return datum;
          });
          return { 'data': data, meta: {} };
      } else if (requestType === "findRecord") {
          var datum = { 'type': schema.modelName };
          datum['attributes'] = _.zipObject(rawPayload.columns, rawPayload.values[0]);
          datum['id'] = datum['attributes']['id'];
          return { 'data': datum, meta: {} };
      } else {
         return { data: {}, meta: {} };
      }
  }

  serialize(snapshot, options) {
    const serializedResource = {
      id: snapshot.id,
      type: snapshot.modelName,
      attributes: snapshot.attributes()
    };

    return serializedResource;
  }
}
