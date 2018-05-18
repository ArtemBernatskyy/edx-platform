import Papa from 'papaparse';

import { csvViewerActions } from './constants';

const fetchCSVDataStart = () => ({
  type: csvViewerActions.fetch.START,
});

const fetchCSVDataSuccess = csvData => ({
  type: csvViewerActions.fetch.SUCCESS,
  csvData,
});

const fetchCSVDataFailure = error => ({
  type: csvViewerActions.fetch.FAILURE,
  error,
});

const fetchCSVData = csvFileUrl => (dispatch) => {
  dispatch(fetchCSVDataStart());
  Papa.parse(csvFileUrl, {
    download: true,
    dynamicTyping: true,
    header: true,
    skipEmptyLines: true,
    trimHeader: true,
    complete: (results) => {
      dispatch(fetchCSVDataSuccess(results.data));
    },
    error: () => {
      dispatch(fetchCSVDataFailure('csv_load_error'));
    },
  });
};

export {
    fetchCSVData,
    fetchCSVDataSuccess,
};
