// The pinned Air Datepicker has no nb locale. Supply its ordinary locale data
// from the browser's existing CLDR implementation; keep the native control.
if (frappe.boot.lang === 'nb' && $.fn.datepicker?.language && !$.fn.datepicker.language.nb) {
    const names = (dates, options) => {
        const formatter = new Intl.DateTimeFormat('nb-NO', {...options, timeZone: 'UTC'});
        return dates.map(date => formatter.format(date));
    };
    const weekdays = Array.from({length: 7}, (_, day) => new Date(Date.UTC(2024, 0, 7 + day)));
    const months = Array.from({length: 12}, (_, month) => new Date(Date.UTC(2024, month, 1)));
    $.fn.datepicker.language.nb = {
        ...$.fn.datepicker.language.en,
        days: names(weekdays, {weekday: 'long'}),
        daysShort: names(weekdays, {weekday: 'short'}),
        daysMin: names(weekdays, {weekday: 'short'}).map(day => day.slice(0, 2)),
        months: names(months, {month: 'long'}),
        monthsShort: names(months, {month: 'short'}),
        today: __('Today'), clear: __('Clear'), firstDay: 1,
    };
}
