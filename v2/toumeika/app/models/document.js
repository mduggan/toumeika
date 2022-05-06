import Model, { attr, belongsTo } from '@ember-data/model';

export default class DocumentModel extends Model {
  @attr('number') year; // the year the doc is about, not publication year - that's in the docset
  @attr('string') note;
  @attr('string') filename;
  @attr('number') pages;
  @attr('number') size;
  @attr('string') url;
  @attr('string') srcurl;
  @belongsTo('group', { async: true }) group;
  @belongsTo docSet;
}
