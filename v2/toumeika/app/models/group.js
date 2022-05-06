import Model, { attr, hasMany, belongsTo } from '@ember-data/model';

export default class GroupModel extends Model {
  @attr('string') name;
  @hasMany('document', { inverse: 'group', async: true }) documents;
  @hasMany('group', { inverse: 'parent', async: true }) children;
  @belongsTo groupType;
}
