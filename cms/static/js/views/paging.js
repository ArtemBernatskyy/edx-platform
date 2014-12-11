define(["underscore", "js/views/baseview", "js/views/feedback_alert", "gettext", "js/views/paging_mixin"],
    function(_, BaseView, AlertView, gettext, PagingMixin) {

        var PagingView = BaseView.extend(PagingMixin).extend({
            // takes a Backbone Paginator as a model

            sortableColumns: {},

            initialize: function() {
                BaseView.prototype.initialize.call(this);
                var collection = this.collection;
                collection.bind('add', _.bind(this.onPageRefresh, this));
                collection.bind('remove', _.bind(this.onPageRefresh, this));
                collection.bind('reset', _.bind(this.onPageRefresh, this));
            },

            onPageRefresh: function() {
                var sortColumn = this.sortColumn;
                this.renderPageItems();
                this.$('.column-sort-link').removeClass('current-sort');
                this.$('#' + sortColumn).addClass('current-sort');
            },

            onError: function() {
                // Do nothing by default
            },

            /**
             * Registers information about a column that can be sorted.
             * @param columnName The element name of the column.
             * @param displayName The display name for the column in the current locale.
             * @param fieldName The database field name that is represented by this column.
             * @param defaultSortDirection The default sort direction for the column
             */
            registerSortableColumn: function(columnName, displayName, fieldName, defaultSortDirection) {
                this.sortableColumns[columnName] = {
                    displayName: displayName,
                    fieldName: fieldName,
                    defaultSortDirection: defaultSortDirection
                };
            },

            sortableColumnInfo: function(sortColumn) {
                var sortInfo = this.sortableColumns[sortColumn];
                if (!sortInfo) {
                    throw "Unregistered sort column '" + sortColumn + '"';
                }
                return sortInfo;
            },

            sortDisplayName: function() {
                var sortColumn = this.sortColumn,
                    sortInfo = this.sortableColumnInfo(sortColumn);
                return sortInfo.displayName;
            },

            setInitialSortColumn: function(sortColumn) {
                var collection = this.collection,
                    sortInfo = this.sortableColumns[sortColumn];
                collection.sortField = sortInfo.fieldName;
                collection.sortDirection = sortInfo.defaultSortDirection;
                this.sortColumn = sortColumn;
            },

            toggleSortOrder: function(sortColumn) {
                var collection = this.collection,
                    sortInfo = this.sortableColumnInfo(sortColumn),
                    sortField = sortInfo.fieldName,
                    defaultSortDirection = sortInfo.defaultSortDirection;
                if (collection.sortField === sortField) {
                    collection.sortDirection = collection.sortDirection === 'asc' ? 'desc' : 'asc';
                } else {
                    collection.sortField = sortField;
                    collection.sortDirection = defaultSortDirection;
                }
                this.sortColumn = sortColumn;
                this.setPage(0);
            }
        });
        return PagingView;
    }); // end define();
