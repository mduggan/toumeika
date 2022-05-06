import Model, { attr } from '@ember-data/model';

export default class DocTypeModel extends Model {
  @attr('number') id;
  @attr('string') name;
}
