import Model, { attr } from '@ember-data/model';

export default class PubTypeModel extends Model {
  @attr('string') name;
}
