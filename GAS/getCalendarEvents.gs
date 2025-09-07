// getMyCalendarEvents.gs

function test() {
  let evs = getMyCalendarEvents();
  let data = eventsToDict(evs);
  Logger.log(data);
}

function doGet() {
  let evs = getMyCalendarEvents();
  let data = eventsToDict(evs);

  ContentService.createTextOutput()
  var output = ContentService.createTextOutput();
  output.setMimeType(ContentService.MimeType.JSON);
  output.setContent(JSON.stringify(data));
  return output;
}

const CALENDAR_ID = "yfkf19961009@gmail.com";
const PRE_RANGE_DAY = 7;
const POST_RANGE_DATE = 7;
const MAX_EVENTS_NUM = 20;

function getMyCalendarEvents() {
  let calendar = CalendarApp.getCalendarById(CALENDAR_ID);

  let now = new Date();
  let start = new Date(now.getFullYear(), now.getMonth() - PRE_RANGE_DAY, 1);
  let end = new Date(now.getFullYear(), now.getMonth() + POST_RANGE_DATE + 1, -1);

  let events = [];
  let pre_events = calendar.getEvents(start, now);
  let post_events = calendar.getEvents(now, end);

  if (pre_events.length + post_events.length > MAX_EVENTS_NUM) {
    pre_events = pre_events.slice(-MAX_EVENTS_NUM/2);
    post_events = post_events.slice(0, (MAX_EVENTS_NUM-pre_events.length));
  }
  events = [...pre_events, ...post_events];

  return events;
}

/**
 * @param {CalendarApp.CalendarEvent[]} events
 */
function eventsToDict(events) {
  let list = [];
  for (let event of events) {
    list.push({
      "title": event.getTitle(),
      "start": event.getStartTime()?.toString(),
      "end": event.getEndTime()?.toString(),
      "description": event.getDescription(),
      "isAllDayEvent": event.isAllDayEvent(),
    });
  }
  return list;
}