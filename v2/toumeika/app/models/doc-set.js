import Model, { attr } from '@ember-data/model';

export default class DocSetModel extends Model {
  @attr('date') published;
  @attr('string') path;
}
