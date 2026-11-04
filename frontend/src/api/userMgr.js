import axios from 'axios';
import { API_BASE_URL } from "@/utils/Constants.js";

export const userLogin = (requestData) => {
  return axios.post(API_BASE_URL + 'login', requestData);
};

export const getUserInfo = () => {
  return axios.get(API_BASE_URL + 'user');
}

export const userLogout = (requestData) => {
  return axios.post(API_BASE_URL + 'logout', requestData);
};

export const getPublicKey = () => {
  return axios.get(API_BASE_URL + 'get_pubkey');
};

